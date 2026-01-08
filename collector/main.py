"""Network device data collector."""
import argparse
import asyncio
import logging
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from netmiko import ConnectHandler
from shared.config import Config
from shared.db import Database
from shared.filters import process_output

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeviceCollector:
    """Collector for a single device."""
    
    def __init__(self, device_config: Dict[str, Any], config: Config):
        """Initialize device collector."""
        self.device_config = device_config
        self.config = config
        self.device_name = device_config['name']
    
    def execute_command(self, command: str, db: Database) -> None:
        """Execute a single command on the device."""
        start_time = time.time()
        ts_epoch = int(start_time)
        
        # Get line exclusions
        command_exclusions = self.config.get_command_line_exclusions(command)
        if command_exclusions is None:
            line_exclusions = self.config.get_global_line_exclusions()
        else:
            line_exclusions = command_exclusions
        
        try:
            # Connect to device
            connection = ConnectHandler(
                device_type=self.device_config['device_type'],
                host=self.device_config['host'],
                port=self.device_config.get('port', 22),
                username=self.device_config['username'],
                password=self.device_config['password'],
            )
            
            # Execute command
            output = connection.send_command(command)
            connection.disconnect()
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Process output
            processed_output, is_filtered, is_truncated, original_line_count = process_output(
                output,
                line_exclusions=line_exclusions,
                output_exclusions=self.config.get_output_exclusions(),
                max_lines=self.config.get_max_output_lines()
            )
            
            # Store in database
            db.insert_run(
                device_name=self.device_name,
                command_text=command,
                ts_epoch=ts_epoch,
                output_text=processed_output,
                ok=True,
                duration_ms=duration_ms,
                is_filtered=is_filtered,
                is_truncated=is_truncated,
                original_line_count=original_line_count
            )
            
            logger.info(f"Executed '{command}' on {self.device_name} in {duration_ms:.2f}ms")
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            
            db.insert_run(
                device_name=self.device_name,
                command_text=command,
                ts_epoch=ts_epoch,
                output_text='',
                ok=False,
                error_message=error_msg,
                duration_ms=duration_ms,
                original_line_count=0
            )
            
            logger.error(f"Error executing '{command}' on {self.device_name}: {error_msg}")
    
    def ping_device(self, db: Database) -> None:
        """Ping the device and store result."""
        ts_epoch = int(time.time())
        ping_host = self.device_config.get('ping_host', self.device_config['host'])
        
        # Validate ping_host to prevent command injection
        # Allow only valid hostnames/IPs (alphanumeric, dots, hyphens, colons for IPv6)
        import re
        if not re.match(r'^[a-zA-Z0-9.\-:]+$', ping_host):
            logger.error(f"Invalid ping_host format: {ping_host}")
            db.insert_ping_sample(
                device_name=self.device_name,
                ts_epoch=ts_epoch,
                ok=False,
                error_message='Invalid ping_host format'
            )
            return
        
        try:
            # Use subprocess to ping with validated host
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', ping_host],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                # Extract RTT from ping output
                rtt_ms = None
                for line in result.stdout.splitlines():
                    if 'time=' in line:
                        try:
                            parts = line.split('time=')[1].split()[0]
                            rtt_ms = float(parts)
                            break
                        except (IndexError, ValueError):
                            pass
                
                db.insert_ping_sample(
                    device_name=self.device_name,
                    ts_epoch=ts_epoch,
                    ok=True,
                    rtt_ms=rtt_ms
                )
            else:
                db.insert_ping_sample(
                    device_name=self.device_name,
                    ts_epoch=ts_epoch,
                    ok=False,
                    error_message='Ping failed'
                )
        
        except Exception as e:
            db.insert_ping_sample(
                device_name=self.device_name,
                ts_epoch=ts_epoch,
                ok=False,
                error_message=str(e)
            )


class Collector:
    """Main collector orchestrator."""
    
    def __init__(self, config: Config):
        """Initialize collector."""
        self.config = config
        self.devices = config.get_devices()
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        
        # Create session database
        session_epoch = int(time.time())
        self.session_db_path = self.data_dir / f'session_{session_epoch}.sqlite3'
        self.current_db_path = self.data_dir / 'current.sqlite3'
        
        self.db = Database(str(self.session_db_path))
        logger.info(f"Created session database: {self.session_db_path}")
        
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.running = True
    
    async def collect_commands(self):
        """Collect commands from all devices."""
        loop = asyncio.get_event_loop()
        futures = []
        
        for device_config in self.devices:
            collector = DeviceCollector(device_config, self.config)
            commands = device_config.get('commands', [])
            
            for command in commands:
                # Run in thread pool to avoid blocking
                future = loop.run_in_executor(
                    self.executor,
                    collector.execute_command,
                    command,
                    self.db
                )
                futures.append(future)
        
        # Wait for all commands to complete
        if futures:
            await asyncio.gather(*futures, return_exceptions=True)
        
        # Atomically update current.sqlite3
        self._update_current_db()
    
    async def collect_pings(self):
        """Collect pings from all devices."""
        loop = asyncio.get_event_loop()
        futures = []
        
        for device_config in self.devices:
            collector = DeviceCollector(device_config, self.config)
            future = loop.run_in_executor(
                self.executor,
                collector.ping_device,
                self.db
            )
            futures.append(future)
        
        if futures:
            await asyncio.gather(*futures, return_exceptions=True)
        
        # Update current.sqlite3 after pings
        self._update_current_db()
    
    def _update_current_db(self):
        """Atomically replace current.sqlite3 with session database."""
        try:
            # Copy session db to temp file
            tmp_path = self.data_dir / 'current.sqlite3.tmp'
            shutil.copy2(self.session_db_path, tmp_path)
            
            # Delete old current.sqlite3 if exists
            if self.current_db_path.exists():
                self.current_db_path.unlink()
            
            # Rename tmp to current
            tmp_path.rename(self.current_db_path)
            
        except Exception as e:
            logger.error(f"Error updating current database: {e}")
    
    async def run(self):
        """Main collection loop."""
        interval_seconds = self.config.get_interval_seconds()
        ping_interval_seconds = self.config.get_ping_interval_seconds()
        
        # Schedule command collection
        async def command_loop():
            while self.running:
                await self.collect_commands()
                await asyncio.sleep(interval_seconds)
        
        # Schedule ping collection
        async def ping_loop():
            while self.running:
                await self.collect_pings()
                await asyncio.sleep(ping_interval_seconds)
        
        # Run both loops concurrently
        await asyncio.gather(
            command_loop(),
            ping_loop()
        )
    
    def stop(self):
        """Stop the collector."""
        self.running = False
        self.executor.shutdown(wait=True)
        self.db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Network device data collector')
    parser.add_argument('--config', required=True, help='Path to config YAML file')
    args = parser.parse_args()
    
    try:
        config = Config(args.config)
        collector = Collector(config)
        
        asyncio.run(collector.run())
    
    except KeyboardInterrupt:
        logger.info("Collector stopped by user")
    except Exception as e:
        logger.error(f"Collector error: {e}", exc_info=True)


if __name__ == '__main__':
    main()
