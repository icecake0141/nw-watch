# Troubleshooting Guide

This guide provides solutions to common issues you may encounter when using nw-watch.

## Table of Contents

- [Connection Issues](#connection-issues)
- [Permission Errors](#permission-errors)
- [Database Issues](#database-issues)
- [Performance Problems](#performance-problems)
- [Configuration Errors](#configuration-errors)
- [Docker Issues](#docker-issues)
- [Web Interface Issues](#web-interface-issues)

## Connection Issues

### Cannot connect to network devices via SSH

**Symptoms:**
- Collector logs show "Connection refused" or "Authentication failed"
- No data appears in the web interface
- Timeout errors when connecting to devices

**Solutions:**

1. **Verify network connectivity:**
   ```bash
   # Test if the device is reachable
   ping <device_ip>
   
   # Test if SSH port is open
   telnet <device_ip> 22
   # or
   nc -zv <device_ip> 22
   ```

2. **Check SSH credentials:**
   ```bash
   # Verify environment variables are set
   echo $DEVICEA_PASSWORD
   
   # Test SSH connection manually
   ssh -p <port> <username>@<device_ip>
   ```

3. **Verify device_type is correct:**
   - Check that `device_type` in config.yaml matches your device
   - See [Netmiko supported devices](https://github.com/ktbyers/netmiko#supported-platforms)
   - Common types: `cisco_ios`, `cisco_nxos`, `juniper_junos`, `arista_eos`

4. **Check firewall rules:**
   - Ensure SSH port (default 22) is not blocked
   - Verify device allows SSH connections from your network
   - Check if IP whitelisting is required on the device

5. **Review SSH connection settings:**
   ```yaml
   ssh:
     persistent_connections: true
     connection_timeout: 100  # Increase if needed
     max_reconnect_attempts: 3
   ```

6. **Enable debug logging:**
   ```python
   # Add to collector/main.py
   logging.basicConfig(level=logging.DEBUG)
   ```

### Connection keeps dropping

**Symptoms:**
- Intermittent connection failures
- Devices show as unreachable periodically
- "Connection reset by peer" errors

**Solutions:**

1. **Adjust SSH keepalive settings:**
   - Some devices may close idle connections
   - Consider reducing `interval_seconds` if commands run infrequently

2. **Check persistent connection settings:**
   ```yaml
   ssh:
     persistent_connections: true
     connection_timeout: 100
     max_reconnect_attempts: 3
     reconnect_backoff_base: 1.0  # Increase for slower retry
   ```

3. **Monitor device resource usage:**
   - High CPU/memory on device may cause connection drops
   - Reduce collection frequency if device is overloaded

4. **Review network stability:**
   - Check for network congestion
   - Look for packet loss between collector and devices

## Permission Errors

### "Permission denied" when accessing configuration

**Symptoms:**
- Cannot read config.yaml
- Error: "Permission denied: 'config.yaml'"

**Solutions:**

1. **Fix file permissions:**
   ```bash
   # Make config readable by the user running the collector
   chmod 600 config.yaml
   chown <user>:<group> config.yaml
   ```

2. **Verify file ownership:**
   ```bash
   ls -la config.yaml
   # Should show the user running the collector as owner
   ```

### "Permission denied" when writing to database

**Symptoms:**
- "Unable to open database file" errors
- Cannot create or update current.sqlite3

**Solutions:**

1. **Fix data directory permissions:**
   ```bash
   # Ensure data directory is writable
   chmod 755 data/
   chown <user>:<group> data/
   ```

2. **For Docker deployments:**
   ```bash
   # Check volume permissions
   docker-compose exec collector ls -la data/
   
   # Fix if needed (run on host)
   sudo chown -R $(id -u):$(id -g) data/
   ```

### "Password environment variable not set"

**Symptoms:**
- "password_env_key 'DEVICEA_PASSWORD' not found" errors
- Authentication failures

**Solutions:**

1. **Set environment variables:**
   ```bash
   # For local installation
   export DEVICEA_PASSWORD="your_password_here"
   export DEVICEB_PASSWORD="your_password_here"
   ```

2. **For Docker deployments:**
   - Ensure `.env` file exists and contains passwords
   - Verify `.env` is in the same directory as docker-compose.yml
   ```bash
   # Check .env file
   cat .env
   ```

3. **Verify variable names match:**
   - Check `password_env_key` in config.yaml matches environment variable name
   ```yaml
   devices:
     - name: "DeviceA"
       password_env_key: "DEVICEA_PASSWORD"  # Must match env var
   ```

## Database Issues

### "Database is locked" errors

**Symptoms:**
- "database is locked" error messages
- Cannot access web interface while collector is running

**Solutions:**

1. **Verify atomic update mechanism:**
   - The system uses session databases and atomic copy
   - Web app reads from `current.sqlite3` (read-only)
   - Collector writes to `session_<timestamp>.sqlite3`

2. **Check disk space:**
   ```bash
   df -h data/
   # Ensure sufficient free space
   ```

3. **Reduce concurrent access:**
   - If running multiple collectors, ensure only one targets the same data directory

4. **For persistent locks:**
   ```bash
   # Stop all services
   # Remove lock files
   rm -f data/*.sqlite3-wal data/*.sqlite3-shm
   # Restart services
   ```

### Database file is corrupted

**Symptoms:**
- "database disk image is malformed" errors
- Web interface shows no data or incomplete data

**Solutions:**

1. **Stop all services first:**
   ```bash
   # Docker
   docker-compose down
   
   # Local
   # Kill collector and webapp processes
   ```

2. **Try to recover with SQLite:**
   ```bash
   # Create backup
   cp data/current.sqlite3 data/current.sqlite3.backup
   
   # Try to recover
   sqlite3 data/current.sqlite3 ".recover" | sqlite3 data/recovered.sqlite3
   mv data/recovered.sqlite3 data/current.sqlite3
   ```

3. **Start fresh if recovery fails:**
   ```bash
   # Backup old data
   mv data/current.sqlite3 data/current.sqlite3.old
   
   # Restart services - collector will create new database
   ```

### Old runs not being cleaned up

**Symptoms:**
- Database grows continuously
- More than configured `history_size` runs exist

**Solutions:**

1. **Verify history_size configuration:**
   ```yaml
   history_size: 10  # Keep last 10 runs per device/command
   ```

2. **Check collector logs:**
   - Cleanup happens after each collection cycle
   - Look for cleanup errors in logs

3. **Manual cleanup:**
   ```bash
   # Use SQLite to inspect
   sqlite3 data/current.sqlite3
   sqlite> SELECT COUNT(*) FROM runs;
   sqlite> SELECT device_id, command_id, COUNT(*) 
           FROM runs GROUP BY device_id, command_id;
   ```

## Performance Problems

### Web interface is slow to load

**Symptoms:**
- Long page load times
- API endpoints respond slowly
- Browser shows "waiting for response"

**Solutions:**

1. **Reduce history_size:**
   ```yaml
   history_size: 5  # Reduce from default 10
   ```

2. **Limit output size:**
   ```yaml
   max_output_lines: 200  # Reduce from default 500
   ```

3. **Add more aggressive filters:**
   ```yaml
   global_filters:
     line_exclude_substrings:
       - "Temperature"
       - "Uptime"
       # Add more patterns to reduce data
   ```

4. **Check database size:**
   ```bash
   ls -lh data/current.sqlite3
   # If very large, consider reducing max_output_lines
   ```

5. **Optimize refresh intervals:**
   ```yaml
   interval_seconds: 10  # Increase from default 5
   ping_interval_seconds: 2  # Increase from default 1
   ```

### High CPU usage in collector

**Symptoms:**
- Collector process uses excessive CPU
- System becomes slow when collector is running

**Solutions:**

1. **Reduce collection frequency:**
   ```yaml
   interval_seconds: 10  # Increase interval
   ```

2. **Use per-command scheduling:**
   ```yaml
   commands:
     - command_text: "show version"
       schedule: "0 */6 * * *"  # Every 6 hours instead of every interval
     - command_text: "show interfaces"
       # Uses interval_seconds for frequently needed data
   ```

3. **Disable persistent connections if problematic:**
   ```yaml
   ssh:
     persistent_connections: false  # Use single connections per command
   ```

4. **Reduce number of concurrent commands:**
   - Consider scheduling expensive commands less frequently
   - Spread commands across time using cron schedules

### High memory usage

**Symptoms:**
- Collector or webapp uses excessive RAM
- Out of memory errors

**Solutions:**

1. **Reduce output size:**
   ```yaml
   max_output_lines: 100  # Reduce significantly
   ```

2. **Add output truncation filters:**
   ```yaml
   global_filters:
     line_exclude_substrings:
       - "Line"  # Filter verbose outputs
   ```

3. **Reduce history size:**
   ```yaml
   history_size: 5  # Keep fewer historical runs
   ```

## Configuration Errors

### "Invalid configuration" error on startup

**Symptoms:**
- Collector or webapp fails to start
- Error message about configuration validation
- Pydantic validation errors

**Solutions:**

1. **Check configuration syntax:**
   ```bash
   # Validate YAML syntax
   python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"
   ```

2. **Review validation error messages:**
   - Error location shown as `field -> subfield -> index`
   - Example: `devices -> 0 -> device_type: Field required`

3. **Common validation issues:**
   - **Missing required fields:**
     ```yaml
     devices:
       - name: "DeviceA"
         host: "192.168.1.1"
         username: "admin"
         password_env_key: "DEVICEA_PASSWORD"
         device_type: "cisco_ios"  # REQUIRED
     ```
   
   - **Invalid ranges:**
     ```yaml
     interval_seconds: 5  # Must be > 0
     history_size: 10     # Must be > 0
     ```
   
   - **Invalid cron schedules:**
     ```yaml
     commands:
       - command_text: "show version"
         schedule: "0 */6 * * *"  # Valid: 5 fields
         # schedule: "invalid"    # INVALID
     ```
   
   - **Invalid port numbers:**
     ```yaml
     port: 22  # Must be 1-65535
     ```
   
   - **Duplicate names:**
     ```yaml
     devices:
       - name: "DeviceA"  # Each device name must be unique
     commands:
       - command_text: "show version"  # Each command_text must be unique
     ```

4. **Check for special characters:**
   - Ensure ping_host doesn't contain command injection characters
   - Valid: `192.168.1.1`, `example.com`, `2001:db8::1`
   - Invalid: `192.168.1.1; rm -rf /`

### Configuration not being reloaded

**Symptoms:**
- Changes to config.yaml don't take effect
- Devices or commands not updated

**Solutions:**

1. **Restart services:**
   ```bash
   # Docker
   docker-compose restart
   
   # Local
   # Ctrl+C on collector and webapp, then restart
   ```

2. **Clear config cache:**
   - Config is cached at startup
   - Must restart to pick up changes

## Docker Issues

### Containers fail to start

**Symptoms:**
- `docker-compose up` fails
- Container exits immediately
- Error in container logs

**Solutions:**

1. **Check logs:**
   ```bash
   docker-compose logs collector
   docker-compose logs webapp
   ```

2. **Verify configuration exists:**
   ```bash
   ls -la config.yaml
   ls -la .env
   ```

3. **Check environment variables:**
   ```bash
   docker-compose config
   # Shows resolved configuration including env vars
   ```

4. **Verify permissions:**
   ```bash
   chmod 644 config.yaml
   chmod 644 .env
   chmod 755 data/
   ```

### Cannot access devices from Docker container

**Symptoms:**
- Collector can't connect to devices
- "No route to host" errors
- Works locally but not in Docker

**Solutions:**

1. **Check network connectivity:**
   ```bash
   # From inside container
   docker-compose exec collector ping <device_ip>
   ```

2. **Use host network mode (if needed):**
   ```yaml
   # In docker-compose.yml
   services:
     collector:
       network_mode: "host"
   ```

3. **Use host.docker.internal for local devices:**
   ```yaml
   # In config.yaml
   devices:
     - host: "host.docker.internal"  # For devices on host machine
   ```

4. **Check firewall rules:**
   - Ensure Docker network can reach devices
   - May need to allow Docker subnet in firewall

### Port 8000 already in use

**Symptoms:**
- "port is already allocated" error
- Cannot start webapp container

**Solutions:**

1. **Find and stop conflicting process:**
   ```bash
   lsof -i :8000
   # or
   sudo netstat -tulpn | grep 8000
   ```

2. **Change port in docker-compose.yml:**
   ```yaml
   services:
     webapp:
       ports:
         - "8080:8000"  # Use port 8080 on host
   ```

## Web Interface Issues

### "No data available" message

**Symptoms:**
- Web interface loads but shows no devices/commands
- Empty tables/lists

**Solutions:**

1. **Verify collector is running:**
   ```bash
   # Docker
   docker-compose ps
   
   # Local
   ps aux | grep collector
   ```

2. **Check database exists:**
   ```bash
   ls -la data/current.sqlite3
   ```

3. **Verify collector has run at least once:**
   ```bash
   # Check database has data
   sqlite3 data/current.sqlite3 "SELECT COUNT(*) FROM runs;"
   ```

4. **Check collector logs for errors:**
   ```bash
   docker-compose logs collector
   # or
   # Check collector terminal output
   ```

### WebSocket connection fails

**Symptoms:**
- "WebSocket connection failed" in browser console
- Falling back to polling mode

**Solutions:**

1. **Verify WebSocket is enabled:**
   ```yaml
   websocket:
     enabled: true
   ```

2. **Check browser console:**
   - F12 → Console tab
   - Look for WebSocket errors

3. **Verify reverse proxy configuration (if using):**
   - Nginx example:
     ```nginx
     location /ws {
         proxy_pass http://localhost:8000;
         proxy_http_version 1.1;
         proxy_set_header Upgrade $http_upgrade;
         proxy_set_header Connection "upgrade";
     }
     ```

4. **Check firewall rules:**
   - Ensure WebSocket connections aren't blocked

### Auto-refresh not working

**Symptoms:**
- Data doesn't update automatically
- Must manually refresh page

**Solutions:**

1. **Check if auto-refresh is paused:**
   - Look for "Auto-refresh is paused" banner
   - Click resume button

2. **Verify collector is running:**
   - New data must be collected for updates to show

3. **Check browser console for errors:**
   - F12 → Console tab
   - Look for JavaScript errors

4. **Try hard refresh:**
   - Ctrl+Shift+R (Windows/Linux)
   - Cmd+Shift+R (Mac)

## Getting Additional Help

If you continue to experience issues:

1. **Enable debug logging:**
   ```python
   # In collector/main.py or webapp/main.py
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Check GitHub issues:**
   - Search for similar issues: https://github.com/icecake0141/nw-watch/issues
   - Create new issue with:
     - Error messages
     - Configuration (sanitized)
     - Steps to reproduce
     - Environment details (Python version, OS, Docker version)

3. **Review logs carefully:**
   - Collector logs show connection and collection issues
   - Webapp logs show HTTP/WebSocket issues
   - Browser console shows JavaScript issues

4. **Test incrementally:**
   - Start with single device
   - Add devices one at a time
   - Verify each works before adding next
