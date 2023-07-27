
'''
Project: Given a list of ingredients, find which stores nearby sell all of those ingredients. Currently
focusing on supermarkets, but could do drugstores as well if this works out

Idea 1: Gather all the ingredients into a database, and then check that with the ingredients list
Idea 2: For each ingredient in the list, perform a search with the bot and see if it
returns any results.
Idea 2 may be easier since it could be challenging to effectively get every product?

Side Note: If I use idea 2, then I could write a function that takes in a list of websites,
and then it could check if it recognizes any of the key brands? This follows the
assumption that websites of different branches will have the same structure
(really just need the search button and food product structure to be the same)

Potential issues for other users:
- Program would not run unless I installed Selenium 4.9.0, due to a timeout error in the requests library.
- Annoying PATH variable things for the geckodriver executable (strange I didn't need to do anything for my laptop?)

'''

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver import Chrome
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains as AC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from difflib import SequenceMatcher

from bs4 import BeautifulSoup
import time

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def scrape_squirrel_aldis():
    '''

    Returns: A list indicating which ingredients were found on the online website.

    Current issues to fix:
    - Items with long names aren't recognized as being in the system. For example, when looking up "Cheez-its",
    it is labeled as "Cheez it cheese crackers, baked snack crackers, etc", and so the sequence matcher incorrectly thinks
    that they are different items
    - How to speed it up? Takes about a minute to load up and search for 5 ingredients, recipes are typically 5-15 ingredients
        - One solution *would* be to do the initial approach of loading all the items off the website prior to any requests,
        as searching a table is much faster than searching through the website
    - Differentiating between specific ingredients is hard, as it recognizes "Grebinskiy's Teriyaki Sauce" as being
    good enough for "Burman's Teriyaki Sauce". This seems very related to issue #1

    '''
    #options = webdriver.ChromeOptions()
    #options.headless = False
    start_time = time.time()
    ingredient_list = ["Grebinskiy's Teriyaki Sauce", "Cheez-its", "Pringles", "bananas", "Haagen Dazs"]
    results = [False] * len(ingredient_list)
    item_threshold = 5
    driver = webdriver.Firefox()
    url = "https://shop.aldi.us/store/aldi/storefront/?current_zip_code=15206&utm_source=yext&utm_medium=local&utm_campaign=brand&utm_content=shopnow_storepage"
    driver.get(url)
    wait = WebDriverWait(driver, 5)
    #time.sleep(6)
    search_button = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@id="search-bar-input"]')))
    print(search_button)
    i = 0
    for ingredient in ingredient_list:
        search_button.click() # this clicks the search button so that we can input our search query
        search_button.clear() # this clears anything in the search box
        search_button.send_keys(ingredient, Keys.ENTER) # enters the ingredient we want to look for, and then begins the search
        #time.sleep(5) # sleep to let the page load (THIS CAN BE BETTER REWRITTEN)
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, '//span[@class="e-8zabzc"]')))
        except:
            print("Elements not found for ingredient", ingredient)
            i += 1
            continue

        page_results = driver.find_elements(By.XPATH, '//span[@class="e-8zabzc"]') # finds all titles of each food item, as this is all we care about
        count = 0
        for item in page_results:
            if count >= item_threshold: # we only want to consider the first k items found, as the results get worse and worse
                break
            similarity = similar(item.text, ingredient)
            print(item.text, similarity)
            if(similarity > 0.65): # if the similarity rating provided by the SequenceMatcher function is high enough, then the item is in the store
                results[i] = True
                break
            count += 1
        i += 1
    driver.quit()
    print(results)
    end_time = time.time()
    print("Total time is ", end_time - start_time)

#scrape_squirrel_aldis()


def giant_eagle_all_brands(driver, wait, action):
    '''
    This function clicks on the Brands button on the Giant Eagle website
    and finds all of the brand names contained there. It removes the count of each brand, since
    we only want the names.
    '''
    element = wait.until(EC.visibility_of_element_located((By.XPATH, '//button[@aria-label="Brand: "]')))
    time.sleep(1)
    action.click(element).perform()
    time.sleep(1) # not sure if necessary, check on this later
    all_brand_names = driver.find_elements(By.XPATH, '//div[@class="sc-cgHAeM jVHret"]')
    result = []
    for brand in all_brand_names:
        text = brand.text
        first_parentheses_idx = text.find('(')
        if first_parentheses_idx != -1:
            text = text[:first_parentheses_idx]
        result.append(text.lower())
    element.click()
    return result
def data_sanitation(ingredients, removable_brand_names):
    '''
    This takes in a list of ingredients and removes certain brand name from the product without altering it in
    another way. The purpose of this is to make the Sequence Matcher more effective.
    However, we don't want to remove the original ingredients, in case people actually want the specific brand

    Notes: The data sanitation part could probably be more effective.
    '''
    shortened_ingredients = []
    for ingr in ingredients:
        ingr_lower = ingr.lower()
        for brand in removable_brand_names:
            if brand in ingr_lower:
                short_ingr = ingr_lower.replace(brand, "")
                shortened_ingredients.append(short_ingr)
    ingredients = ingredients + shortened_ingredients
    return ingredients

def print_ingredients(ingredients, line_width, length):
    count = 0
    while count < length:
        for j in range(line_width):
            if count + j < length:
                print(ingredients[count + j])
        print("\n")
        count += line_width

def scrape_squirrel_giant_eagle():
    '''

    The purpose of this function is to scrape the Giant Eagle website based in Squirrel Hill.
    It takes the products it finds and puts it into a list. I can then search through
    this list later to see if anything matches target ingredient list. This should
    supposedly be fast, as any store should not stock more than 10000 unique items.

    Current Issues to Fix:
    - Running into the stale exception very frequently. It is unclear why this happens,
    since I am waiting for the elements to appear, and I only interact with those elements.
    May need to understand presence_of vs visibility_of better? Unclear if this is
    a serious issue, but I just re-run the prompt and it seems to work fine
        - Edit: If I have time.sleep(3) enabled, I don't get stale exceptions
    - Serious issue: Certain products are never captured by webscraper. In the client
    opened by the bot, these products simply don't show up on the webpage. No ideas
    behind the reason why yet. (On average, 5-10% products are missed. These tend
    to be towards the bottom of the list; e.g., for the candy section, the last 6
    candies + a hershey product around the middle/bottom were skipped)
        - Edit: Fullscreening my window significantly reduced this error rate? Now I only
        miss the hershey product... strange. Maybe it has something to do with how much
        I scroll down by?

    '''
    options = FirefoxOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    action = AC(driver)
    url = "https://shop.gianteagle.com/squirrel-hill/search?cat=20&page=9"
    driver.get(url)
    #driver.maximize_window() # makes the window full_screen
    wait = WebDriverWait(driver, 15) # wait at most 10 seconds for anything to load
    #all_brands = giant_eagle_all_brands(driver, wait, action)
    all_ingredients = []
    try:
        # if we are in category "x" of the website, it clicks on this word x on the page
        # this is necessary because we need the page-down command to work
        element = wait.until(EC.visibility_of_element_located((By.XPATH, '//h1[@class="sc-gJSbpZ kGDYpn"]')))
        element.click()
    except:
        # if the page doesn't load in time (namely 10 seconds), we quit the program
        print("Page did not load in time")
        driver.quit()
        return
    driver.get_screenshot_as_file("screenshot1.png")
    '''
    # we get the element corresponding to the entire product list to get the size of it.
    # this is used so that we know how much to scroll down by
    product_list = driver.find_element(By.XPATH, '//div[@class="ProductsList"]')
    size = product_list.size
    height,width = int(size['height']), int(size['width'])
    # when we scroll down in the while loop, we scroll from the center of the bottom of the page
    scroll_origin = ScrollOrigin.from_viewport(width // 2, height)
    
    (we've commented this out due to swapping back to original scrolling method, which is just using
    page down keys)
    '''
    count = 0
    # count is used to limit the number of total iterations that we run for
    first_item_of_prev_iter = ""
    first_item_of_next_iter = ""
    #driver.get_screenshot_as_file("screenshot2.png")

    counter = 0
    # counter is used to check how many iterations we've gotten
    # the same first element.
    start_time = time.time()
    while count < 100000:
        try:
            # find all product names on the page that load
            items = wait.until(EC.presence_of_all_elements_located((By.XPATH, '//div[@class="sc-fbAgdq bNmZPW"]')))
            # get the first product name that is in the list. the logic below is used
            # to check if we've hit the bottom of the page, and we keep getting
            # the same results
            first_item_of_next_iter = items[0].text
            if first_item_of_next_iter == first_item_of_prev_iter:
                counter += 1
                if counter > 10:
                    break
            else:
                counter = 0
            # this may add duplicates to our list, but we don't care
            for item in items:
                all_ingredients.append(item.text)
        except Exception as e:
            # this program frequently gets stale exceptions in the try statement above
            # what this does, essentially, is it retries loading the elements that show up
            # while ONLY changing the count number. this problem is reduced if we implement
            # some forced waiting at the start of the while loop, e.g. time.sleep(3)
            #print("\n", "Throwed error on count", count, "\n", e)
            count += 1
            continue
        # scrolls down the page by the height of the product box, so that we always see an entire page of new items
        '''
        #action.scroll_from_origin(scroll_origin,0,height).perform()
        Spent quite a while trying to get this to work, but it seems to not work in headless mode, so we're just
        going back to the original method
        '''
        action.send_keys(Keys.PAGE_DOWN).send_keys(Keys.PAGE_DOWN).send_keys(Keys.PAGE_DOWN).perform()
        count += 1
        # part of the logic in checking if we've reached the bottom
        first_item_of_prev_iter = first_item_of_next_iter

    end_time = time.time()
    driver.get_screenshot_as_file("screenshot3.png")
    print("The time needed for the loop to complete is", end_time - start_time)
    # removes all duplicates from the list, while maintaining the same
    # relative order of the items. there should be quite a lot, so this
    # is a necessary step
    all_ingredients = list(dict.fromkeys(all_ingredients))
    #all_ingredients = data_sanitation(all_ingredients, all_brands)
    ln = len(all_ingredients)
    print_ingredients(all_ingredients, 5, ln)
    print(ln)
    # writes the results to a file. after all, we don't want to be rerunning this everytime a user makes a request
    # instead, we should be loading up the file and searching the results on here
    with open('ingredients_output.txt', 'w') as f:
        for item in all_ingredients:
            # write each item on a new line
            f.write(f"{item}\n")
    driver.quit()

# call the function to scrape Giant Eagle website
scrape_squirrel_giant_eagle()

def check_giant_eagle_store(ingredient_list):
    ln = len(ingredient_list)
    res = [False] * ln
    with open('ingredients_output.txt') as f:
        stocked_ingredients = f.read().splitlines()
    for i in range(ln):
        item = ingredient_list[i]
        maxim = 0
        for stocked_ingr in stocked_ingredients:
            maxim = max(maxim, similar(item, stocked_ingr))
        print(maxim)
        if maxim > 0.65:
            res[i] = True
    return res

check_giant_eagle_store(["banana", "pringles", "dark chocolate", "blurpies", "Kosher Apple Pie"])
