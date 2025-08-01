from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import re
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

API_KEY = os.getenv("API_KEY")


def generate_business_reply(review):
    client = genai.Client(api_key=API_KEY)
    if review == "":
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"You are an assistant responding to positive Google reviews that contain only a positive rating with no text or name. Write a one-sentence response that thanks the reviewer for their positive review.",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)  # Disables thinking
            ),
        )
    else:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"You are a business owner, briefly politely and warmley respond to the following review someone left for your business, without including the reviewers name:  {review}",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)  # Disables thinking
            ),
        )

    return response.text


options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")

# Launch the browser
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 15)

# 1. Open Sprout Social
driver.get("https://sproutsocial.com/")

# 2. wait for the user to login
button = WebDriverWait(driver, 300).until(
    EC.element_to_be_clickable((By.XPATH, "//button[@data-qa-button='Group Picker']"))
)
button.click()

# get total number of businesses
card_count = len(WebDriverWait(driver, 3).until(
    EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'DrawerItem__Card')]"))
))
print(f"total businesses loaded: {card_count}")
# 1 navigate to reviews page
driver.get("https://app.sproutsocial.com/reviews/all")
# 2 loop through each company
previous_name = ""
last_business_blank = True
for i in range(card_count):
    time.sleep(1)

    # Re-fetch the card each time to avoid stale element
    if i == 0 or last_business_blank == True:
        button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-qa-button='Group Picker']"))
        )
        button.click()
        last_business_blank = False

    cards = WebDriverWait(driver, 5).until(
        EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'DrawerItem__Card')]"))
    )
    card = cards[i]
    label = card.get_attribute("aria-label")
    print(f"########################{label}########################")


    #######used for businesses with ' or " in the name
    def escape_xpath_string(s):
        if '"' in s and "'" in s:
            parts = s.split("'")
            return "concat(" + ", \"'\", ".join([f"'{part}'" for part in parts]) + ")"
        elif "'" in s:
            return f'"{s}"'  # wrap with double quotes
        else:
            return f"'{s}'"  # wrap with single quotes


    xpath_label = escape_xpath_string(label)

    xpath = f"//div[@aria-label={xpath_label}]"

    button = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )

    # click in the middle of the button to avoid click interception
    actions = ActionChains(driver)
    actions.move_to_element(button).click().perform()

    # print(f"previous name: {previous_name}")
    # Wait until first review name changes, if no reviews skip to the next iteration
    try:
        WebDriverWait(driver, 5).until(
            lambda d: d.find_element(By.XPATH, "(//h2[@data-qa-name])[1]").text.strip() != previous_name
        )
        previous_name = driver.find_element(By.XPATH, "(//h2[@data-qa-name])[1]").text.strip()
    except:
        last_business_blank = True
        continue


    # Wait until all reviews are fully loaded (count stabilizes)
    def reviews_loaded(driver):
        xpath = "//div[@data-qa-message-type='gmb_review' or @data-qa-message-type='yelp_review']"
        prev_count = -1
        for _ in range(5):
            elements = driver.find_elements(By.XPATH, xpath)
            count = len(elements)
            if count == prev_count:
                return elements
            prev_count = count
            time.sleep(1)
        return elements


    ###########load reviews, if no reviews skip to next iteration
    try:
        reviews = WebDriverWait(driver, 5).until(reviews_loaded)
    except:
        last_business_blank = True
        continue
    # iterate through reviews
    for review in reviews:
        try:
            # print name
            name_element = review.find_element(By.XPATH, ".//h2[@data-qa-name]")
            # print(name_element.text.strip())
            # print rating
            rating_element = review.find_element(By.XPATH, ".//div[contains(@class, 'hKGnEb')]")
            # print(int(rating_element.text.strip()[0]))
            # print message
            try:
                message_element = review.find_element(By.XPATH, ".//div[@data-qa-message-text]")
                message_text = message_element.text.strip()
                # print(message_text)
            except:
                message_text = ""
                # print(message_text)
            # print reply status
            try:
                # Locate the SVG element whose 'data-qa-icon-svg' attribute contains the word 'reply'
                reply_element = review.find_element(By.XPATH, ".//span[contains(@data-qa-icon, 'reply')]")

                # Get the value of the 'data-qa-icon-svg' attribute
                reply_value = reply_element.get_attribute('data-qa-icon')

                # Check if it contains 'outline' or 'solid'
                if 'outline' in reply_value:
                    needs_reply = True
                elif 'solid' in reply_value:
                    needs_reply = False
                else:
                    needs_reply = False

            except NoSuchElementException:
                needs_reply = False
            # print(f"needs_reply = {needs_reply}")
            # print complete Status
            try:
                # Locate the SVG element whose 'data-qa-icon-svg' attribute contains the word 'circle-check'
                complete_element = review.find_element(By.XPATH, ".//span[contains(@data-qa-icon, 'circle-check')]")

                # Get the value of the 'data-qa-icon-svg' attribute
                complete_value = complete_element.get_attribute('data-qa-icon')

                # Check if it contains 'outline' or 'solid'
                if 'outline' in complete_value:
                    needs_complete = True
                elif 'solid' in complete_value:
                    needs_complete = False
                else:
                    needs_complete = False
            except NoSuchElementException:
                needs_complete = False
            # print(f"needs_complete = {needs_complete}")

            # 4. if positive rating, no reply, and not marked as complete, generate review
            if int(rating_element.text.strip()[0]) > 3 and needs_reply == True and needs_complete == True:
                reply_button = WebDriverWait(driver, 5).until(
                    lambda d: review.find_element(By.XPATH, ".//button[@aria-label='Reply']"))
                reply_button.click()

                editable_div = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, ".//div[@contenteditable='true']"))
                )

                # Click inside the editable field
                editable_div.click()

                # type the review
                review_reply = generate_business_reply(message_text)
                editable_div.send_keys(review_reply)

                # open list of approvers
                approver_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@data-qa-button='reply-approvers-select']"))
                )
                approver_button.click()
                time.sleep(0.3)
                # select morgan
                li_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//li[@data-qa-menu-item='Morgan Asuke']"))
                )
                li_element.click()

                # submit review
                button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@data-qa-button='Submit For Approval']"))
                )
                button.click()
                time.sleep(1.5)
                close_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'TakeoverTitle-close')]"))
                )
                close_button.click()

                print("reply auto-generated")

        except Exception as e:
            # print("Could not extract name:", e)
            continue

    time.sleep(4)

    if i != card_count - 1:
        button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-qa-button='Group Picker']"))
        )
        button.click()
