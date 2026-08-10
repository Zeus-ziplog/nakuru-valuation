import json
import subprocess
import sys
import os

def handler(request, response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    
    if request.method != 'POST':
        return response.json({'error': 'Method not allowed'}, status=405)
    
    try:
        result = subprocess.run(
            [sys.executable, 'src/scraper.py'],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            return response.json({
                'success': False,
                'error': result.stderr
            }, status=500)
        
        return response.json({
            'success': True,
            'message': 'Data refreshed successfully',
            'output': result.stdout
        })
        
    except subprocess.TimeoutExpired:
        return response.json({
            'success': False,
            'error': 'Scraper timed out after 120 seconds'
        }, status=504)
    except Exception as e:
        return response.json({
            'success': False,
            'error': str(e)
        }, status=500)
