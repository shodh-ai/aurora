import asyncio
import traceback
from playwright.async_api import async_playwright

class BrowserManager:
    def __init__(self):
        self.browser = None
        self.page = None
        self.current_url = "https://www.google.com"

    async def start_browser(self):
        p = await async_playwright().start()
        self.browser = await p.webkit.launch(headless=True)
        self.page = await self.browser.new_page()
        await self.page.goto(self.current_url)

    async def close_browser(self):
        if self.browser:
            await self.browser.close()

    async def navigate(self, url):
        if self.page:
            self.current_url = url
            # Wait until the page is fully loaded and network is idle
            await self.page.goto(url, wait_until="load")

    async def get_screenshot(self):
        if self.page:
            return await self.page.screenshot(type="jpeg", quality=70, timeout=60000)
        return None

    async def get_page_content_as_text(self):
        if self.page:
            # Extracts the text content of the page, which is useful for analysis.
            return await self.page.inner_text('body')
        return None

    async def execute_interaction(self, interaction_code: str):
        if not self.page:
            return "Browser not initialized."
        try:
            # The user code is a series of await calls. We wrap it in an async function.
            code_to_exec = (
                "async def __interaction():\n" +
                "\n".join(f"    {line}" for line in interaction_code.splitlines())
            )
            
            # The 'page' object will be available in the scope of the exec function
            exec_scope = {'page': self.page, 'asyncio': asyncio}
            
            # Define the __interaction function inside the scope
            exec(code_to_exec, exec_scope)
            
            # Get the function from the scope
            interaction_func = exec_scope['__interaction']
            
            # Now, await the function call
            await interaction_func()

            return "Interaction executed successfully."
        except Exception as e:
            print(f"An error occurred during interaction: {traceback.format_exc()}")
            return f"An error occurred during interaction: {traceback.format_exc()}"

browser_manager = BrowserManager()



