import asyncio
import sys
import traceback
from urllib.parse import urlparse
import aiohttp
import time
import os
from mcp import ClientSession
from mcp.client.sse import sse_client
import json


class MCPClient:
    """Client for interacting with the Playwright MCP server."""
    
    def __init__(self, server_url=None):
        """Initialize the MCP client.
        
        Args:
            server_url: URL of the MCP server's SSE endpoint
        """
        self.server_url = os.getenv("PLAYWRIGHT_MCP_URL", "http://localhost:8931/sse")
        self.session = None
        self.streams = None
        self.is_connected = False
     
    def print_items(self, name, result):
        """Print items with formatting.

        Args:
            name: Category name (tools/resources/prompts)
            result: Result object containing items list
        """
        print(f"\nAvailable {name}:")
        items = getattr(result, name)
        if items:
            for item in items:
                print(" *", item)
        else:
            print("No items available")
    
    async def ping_server(self, url=None):
        """Ping the server to check if it's available.
        
        Args:
            url: The SSE endpoint URL
            
        Returns:
            bool: True if server is reachable, False otherwise
        """
        # Convert SSE endpoint URL to base URL
        url = url or self.server_url
        # base_url = url.replace('/sse', '')
        
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    elapsed = time.time() - start_time
                    print(f"Server ping response: {response.status} (latency: {elapsed:.3f}s)")
                    return True
        except Exception as e:
            print(f"Failed to ping server: {e}")
            return False
    
    async def connect(self):
        """Connect to the MCP server."""
        print(f"Connecting to Playwright MCP server at {self.server_url}...")

        if urlparse(self.server_url).scheme not in ("http", "https"):
            print("Error: Server URL must start with http:// or https://")
            return False

        if not await self.ping_server(self.server_url):
            print("Error: Unable to connect to server. Please check the server URL and try again.")
            return False

        try:
            # Use the sse_client as a context manager to get read and write streams
            self.sse_context = sse_client(self.server_url)
            self.streams = await self.sse_context.__aenter__()
            print(f"Connected to MCP server at {self.server_url}")
            
            # Create an MCP client session with the streams
            self.session = ClientSession(self.streams[0], self.streams[1])
            # await self.session.initialize()
            print(f"Initialized session with MCP server at {self.server_url}")
            
            self.is_connected = True
            return True

        except Exception as e:
            print(f"Error connecting to MCP server: {e}")
            traceback.print_exception(type(e), e, e.__traceback__)
            return False

            
    async def playwright_navigate(self, url, browser_type="chromium", timeout=100000, headless=True):
        """Navigate to a URL.
        
        Args:
            url: URL to navigate to
            browser_type: Browser type to use (chromium, firefox, webkit)
            timeout: When to consider navigation as finished
            headless: Whether to run browser in headless mode
            
        Returns:
            dict: Result of the navigation
        """
        print("it is was here 1")
        if not self.is_connected or not self.session:
            print("it is was here 1.5")
            self.is_connected = await self.connect()
            print("it is was here 1.6")
            if not self.is_connected:
                raise Exception("Failed to connect to MCP server")
        
        print("it is was here 2")
        
        result = await self.session.call_tool(
            name="playwright_navigate",
            arguments={
                "url": url,
                "timeout": timeout,
                "waitUntil": "load",
                "headless": headless
            }
        )
        print(result)
        print("it is was here 3")
        return result
        
    async def playwright_visible_html(self, ship_name):
        """Get the HTML content of the current page.
        
        Args:
            ship_name: Name of the ship to save HTML content for
            
        Returns:
            str: HTML content of the current page
        """
        if not self.is_connected or not self.session:
            self.is_connected = await self.connect()
            
            if not self.is_connected:
                raise Exception("Failed to connect to MCP server")
                
        # Use a default selector to get the visible HTML content
        selector = "body"
        html_result = await self.session.call_tool(
            name="playwright_visible_html",
            arguments=json.dumps({
                "selector": selector
            })
        )
        with open(f"{ship_name}.html", "w") as f:
            f.write(html_result)
        return html_result
        
    async def playwright_close(self):
        """Close the browser and release all resources."""
        if not self.is_connected or not self.session:
            return
        
        try:
            # Close the browser
            await self.session.playwright_close()
            
            # Clean up session and streams
            if self.session:
                await self.session.close()
            
            self.is_connected = False
            self.session = None
            self.streams = None
            print("Browser closed and resources released.")
        except Exception as e:
            print(f"Error closing browser: {e}")
            traceback.print_exception(type(e), e, e.__traceback__)
            # Force reset the connection state
            self.is_connected = False
            self.session = None
            self.streams = None
            
    async def cleanup(self):
        """Clean up all resources and connections.
        
        This method should be called when the application is shutting down.
        """
        if self.is_connected:
            await self.playwright_close()
        
        # Ensure all resources are released
        self.is_connected = False
        self.session = None
        self.streams = None
        print("MCP client resources cleaned up.")