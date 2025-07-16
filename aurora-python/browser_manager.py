import traceback
import json
import logging
from playwright.async_api import async_playwright, Page, Playwright, Locator
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class BrowserManager:
    def __init__(self, headless: bool = True):
        self.playwright: Playwright | None = None
        self.browser = None
        self.page: Page | None = None
        self.headless = headless

        self.clickable_elements: List[Dict[str, Any]] = []
        self.form_elements: List[Dict[str, Any]] = []

        self.CLICKABLE_SELECTOR = "a, button, [role='button'], input[type='submit'], input[type='button'], input[type='reset']"
        self.FORM_SELECTOR = 'input:not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="checkbox"]):not([type="radio"]), textarea'

    async def start_browser(self):
        print("--- Starting Browser ---")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()
        await self.navigate("https://www.google.com")
        print("--- Browser Started ---")

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("--- Browser Closed ---")

    async def navigate(self, url: str):
        if self.page:
            logger.info(f"--- Navigating to {url} ---")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            self.clickable_elements = []
            self.form_elements = []
            return {"status": "success", "url": self.page.url}

    async def get_screenshot(self, full_page: bool = False) -> dict | None:
        if not self.page:
            return None
        try:
            screenshot = await self.page.screenshot(
                type="jpeg", quality=80, timeout=60000, full_page=full_page
            )
            return {"screenshot": screenshot}
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None

    async def _get_elements(self, selector: str, cache_list: list):
        if not self.page:
            return
        try:
            locators = await self.page.locator(selector).all()
            cache_list.clear()

            for i, locator in enumerate(locators):
                cache_list.append({"id": i, "locator": locator})
        except Exception as e:
            logger.error(f"Error getting elements with selector '{selector}': {e}")

    async def get_clickable_elements(self):
        await self._get_elements(self.CLICKABLE_SELECTOR, self.clickable_elements)
        return f"Found {len(self.clickable_elements)} clickable elements."

    async def get_form_elements(self):
        await self._get_elements(self.FORM_SELECTOR, self.form_elements)
        return f"Found {len(self.form_elements)} form elements."

    async def _get_element_details_for_llm(
        self, element_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Helper to extract detailed information from a Playwright locator."""
        locator = element_info["locator"]

        if not await locator.is_visible():
            return None

        tag = await locator.evaluate("el => el.tagName.toLowerCase()")
        text = (await locator.inner_text() or "").strip().replace('"', "'")
        attributes = await locator.evaluate(
            "el => Array.from(el.attributes).reduce((obj, attr) => { obj[attr.name] = attr.value; return obj; }, {})"
        )

        return {
            "id": element_info["id"],
            "tag": tag,
            "text": text,
            "attributes": attributes,
        }

    async def get_clickable_elements_for_llm(
        self, start_index: int = 0, elements: int = 20
    ) -> str:
        llm_friendly_elements = []
        paginated_elements = self.clickable_elements[
            start_index : start_index + elements
        ]
        for el_info in paginated_elements:
            details = await self._get_element_details_for_llm(el_info)
            if details:
                llm_friendly_elements.append(details)
        return json.dumps(llm_friendly_elements, indent=2)

    async def get_form_elements_for_llm(
        self, start_index: int = 0, elements: int = 20
    ) -> str:
        llm_friendly_elements = []
        paginated_elements = self.form_elements[start_index : start_index + elements]
        for el_info in paginated_elements:
            details = await self._get_element_details_for_llm(el_info)
            if details:
                llm_friendly_elements.append(details)
        return json.dumps(llm_friendly_elements, indent=2)

    async def click_element(self, element_id: int):
        if not self.page:
            return "Browser not initialized."

        target_element_info = next(
            (el for el in self.clickable_elements if el["id"] == element_id), None
        )
        if not target_element_info:
            return f"Error: Element with ID '{element_id}' not found in the clickable elements cache."

        locator = target_element_info["locator"]

        logger.info(f"--- Clicking Element ID {element_id} ---")
        try:
            await locator.click(timeout=10000)
            return f"Successfully clicked element {element_id}."
        except Exception as e:
            return f"Error clicking element {element_id}: {traceback.format_exc()}"

    async def type_into_element(
        self, element_id: int, text_to_type: str, submit: bool = False
    ):
        if not self.page:
            return "Browser not initialized."

        target_element_info = next(
            (el for el in self.form_elements if el["id"] == element_id), None
        )
        if not target_element_info:
            return f"Error: Element with ID '{element_id}' not found in the form elements cache."

        locator = target_element_info["locator"]

        logger.info(f"--- Typing '{text_to_type}' into Element ID {element_id} ---")
        try:
            await locator.fill(text_to_type, timeout=10000)
            if submit:
                await locator.press("Enter")
            return f"Successfully typed into element {element_id}."
        except Exception as e:
            return f"Error typing into element {element_id}: {traceback.format_exc()}"


browser_manager = BrowserManager()
