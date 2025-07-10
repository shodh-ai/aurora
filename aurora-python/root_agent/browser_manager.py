import asyncio
import traceback
from playwright.async_api import async_playwright

class BrowserManager:
    def __init__(self):
        self.browser = None
        self.page = None
        self.current_url = "https://www.google.com"
        self.last_sent_screenshot_bytes: bytes | None = None

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
            screenshot_data = await self.page.screenshot(type="jpeg", quality=70, timeout=60000)
            self.last_sent_screenshot_bytes = screenshot_data
            return screenshot_data
        return None

    async def get_elements_info(self, selector: str = None) -> str:
        """Returns information about interactive elements on the current page, optionally filtered by a Playwright selector.

        Args:
            selector (str, optional): A Playwright selector string (e.g., 'button', 'input[type="text"]', 'div.some-class'). If provided, only elements matching this selector will be returned. Defaults to None.
        """
        if not self.page:
            return "Browser not initialized."

        elements_info = []
        # Define common interactive elements and their attributes
        selectors = [
            "button", "a", "input", "textarea", "select",
            "[role='button']", "[role='link']", "[role='textbox']",
            "[aria-label]", "[placeholder]", "[data-testid]"
        ]

        print("--- Starting get_elements_info ---")
        if selector:
            elements = await self.page.locator(selector).all()
        else:
            elements = []
            for s in selectors:
                elements.extend(await self.page.locator(s).all())

        for element in elements:
            try:
                tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                text_content = await element.text_content()
                aria_label = await element.get_attribute("aria-label")
                role = await element.get_attribute("role")
                placeholder = await element.get_attribute("placeholder")
                data_testid = await element.get_attribute("data-testid")
                
                # Attempt to create a robust locator
                locator_parts = []
                if aria_label:
                    locator_parts.append(f"page.get_by_label('{aria_label}')")
                if role:
                    locator_parts.append(f"page.get_by_role('{role}', name='{text_content or aria_label or ''}', exact=False)")
                if text_content and tag_name in ["button", "a"]:
                    locator_parts.append(f"page.get_by_text('{text_content}', exact=False)")
                if placeholder:
                    locator_parts.append(f"page.get_by_placeholder('{placeholder}')")
                if data_testid:
                    locator_parts.append(f"page.get_by_test_id('{data_testid}')")
                
                # Fallback to CSS selector if no specific locator can be formed
                if not locator_parts:
                    element_id = await element.get_attribute('id')
                    id_suffix = f'[id="{element_id}"]' if element_id else ''
                    locator_parts.append(f"page.locator('{tag_name}{id_suffix}')")

                elements_info.append({
                    "tag_name": tag_name,
                    "text_content": text_content.strip() if text_content else "",
                    "aria_label": aria_label,
                    "role": role,
                    "placeholder": placeholder,
                    "data_testid": data_testid,
                    "locator": " or ".join(locator_parts)
                })
            except Exception as e:
                print(f"Error processing element: {e}")
                continue
        print(f"--- Finished get_elements_info: Found {len(elements_info)} elements ---")
        # print(f"Sample elements_info: {elements_info[:2]}") # Print first 2 elements for brevity
        return elements_info

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



