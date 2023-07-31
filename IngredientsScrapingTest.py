
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

Thoughts about Similarity Check:
- Some products have very long names, such as "Cheez-It Cheese Crackers, Baked Snack Crackers, Lunch Snacks, Original". Thus,
when looking up items such as "Cheez-It Crackers", token_sort_ratio does not do well, but token_set_ratio is perfect.
However, token_set_ratio is too broad, since I could be looking for "lemon" and get "lemon cheesecake" instead with token_set_ratio,
so token_sort_ratio would work correctly here but token_set_ratio would not. It seems difficult to differentiate between these two scenarios,
so I wonder if there is some better way to deal with this
- MAIN ISSUE: It is very difficult, if not impossible, to do this with token similarity. Consider "honey" with "100% honey"
vs "dark chocolate" with "dark chocolate ice cream". With thefuzz's token_sort_ratio, the honey is ranked closer to honeydew than 100% honey,
which should be incorrect. However, with token_set_ratio, then dark chocolate and dark chocolate ice cream have a 100% similarity, even though
the second item is very different. This suggests that there needs to be some understanding behind the titles of each product,
so some sort of machine learning is required.

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
from thefuzz import fuzz
from thefuzz import process
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import time

def similar(a, b):
    return fuzz.token_sort_ratio(a,b)

def aldis_all_brands(driver, wait):
    elements = wait.until(EC.visibility_of_all_elements_located((By.XPATH, '//button[@class="e-1ff8o8k"]')))
    for i in range(len(elements)):
        elem = elements[i]
        button_name = elem.find_element(By.XPATH, ".//span").text
        if button_name == "Brands":
            elem.click()
            break
        if i == len(elements) - 1:
            return []
    time.sleep(1)  # not sure if necessary, check on this later
    all_brand_names = driver.find_elements(By.XPATH, '//label[@class="e-1rv1880"]')
    result = []
    for brand in all_brand_names:
        text = brand.text
        result.append(text.lower())
    return result

def has_numbers(inputString):
    return any(char.isdigit() for char in inputString)

def aldis_sanitize_data(ingredients, removable_brand_names):
    shortened_ingredients = []
    '''for ingr in ingredients:
        for brand in removable_brand_names:
            if brand in ingr:
                short_ingr = ingr.replace(brand, "")
                short_ingr = short_ingr.replace(",", "")
                shortened_ingredients.append(short_ingr)
    ingredients = ingredients + shortened_ingredients
    '''
    stop_words = set(stopwords.words('english'))
    common_food_words = {"pack","count","oz", "lb", "fat", "lean", "value", "ct", "g", "pound", "reduced", "fridge", "original", "full", "half", "size"}
    stop_words = stop_words | common_food_words | set(removable_brand_names) # take the union of all sets
    for ingr in ingredients:
        tokenized_ingr = word_tokenize(ingr)
        word = [w for w in tokenized_ingr if w not in stop_words and not has_numbers(w)]
        shortened_ingredients.append(word)
    ingredients = ingredients + shortened_ingredients
    return ingredients

def scrape_squirrel_aldis(ingredient_list):
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
    options = FirefoxOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    start_time = time.time()
    ingredient_list = [x.lower() for x in ingredient_list]
    results = [False] * len(ingredient_list)
    url = "https://shop.aldi.us/store/aldi/storefront/?current_zip_code=15206&utm_source=yext&utm_medium=local&utm_campaign=brand&utm_content=shopnow_storepage"
    driver.get(url)
    wait = WebDriverWait(driver, 5)
    search_button = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@id="search-bar-input"]')))
    i = 0
    for ingredient in ingredient_list:
        search_button.click() # this clicks the search button so that we can input our search query
        search_button.clear() # this clears anything in the search box
        search_button.send_keys(ingredient, Keys.ENTER) # enters the ingredient we want to look for, and then begins the search
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, '//span[@class="e-8zabzc"]')))
        except:
            print("Elements not found for ingredient", ingredient)
            i += 1
            continue
        all_brands = []
        try:
            all_brands = aldis_all_brands(driver, wait)
            print(all_brands)
        except:
            print("No brands button")
        page_results = driver.find_elements(By.XPATH, '//span[@class="e-8zabzc"]') # finds all titles of each food item, as this is all we care about
        stocked_items = [item.text.lower() for item in page_results]
        stocked_items = aldis_sanitize_data(stocked_items, all_brands)
        (best_match, score) = process.extractOne(ingredient, stocked_items, scorer=fuzz.token_sort_ratio)
        if score > 70:
            results[i] = True
        #print(score, best_match, "\n")

        i += 1
    driver.quit()
    #print(results)
    end_time = time.time()
    #print("Total time is ", end_time - start_time)
    return results

def giant_eagle_all_brands(driver, wait):
    '''
    This function clicks on the Brands button on the Giant Eagle website
    and finds all of the brand names contained there. It removes the count of each brand, since
    we only want the names.
    '''
    element = wait.until(EC.visibility_of_element_located((By.XPATH, '//button[@aria-label="Brand: "]')))
    time.sleep(2)
    element.click()
    time.sleep(2) # not sure if necessary, check on this later
    all_brand_names = driver.find_elements(By.XPATH, '//div[@class="sc-cgHAeM jVHret"]')
    result = []
    for brand in all_brand_names:
        text = brand.text
        first_parentheses_idx = text.find('(')
        if first_parentheses_idx != -1:
            text = text[:first_parentheses_idx]
        text = text.replace("'", "")
        result.append(text.lower())
    element.click()
    return result
def giant_eagle_data_sanitation(ingredients, removable_brand_names):
    '''
    This takes in a list of ingredients and removes certain brand name from the product without altering it in
    another way. All commas are removed as well.
    We append the shortened products to the end instead of changing the original product,
    incase the specific brand name is wanted

    Notes: The data sanitation part could probably be more effective.
    '''
    shortened_ingredients = []
    plural_brands = [brand + "s" for brand in removable_brand_names]
    '''for ingr in ingredients:
        ingr_lower = ingr.lower()
        for brand in removable_brand_names:
            if brand in ingr_lower:
                short_ingr = ingr_lower.replace(brand, "")
                short_ingr = short_ingr.replace(",", "")
                shortened_ingredients.append(short_ingr)
    ingredients = ingredients + shortened_ingredients
    ingredients = [x.lower() for x in ingredients]
    '''
    stop_words = set(stopwords.words('english'))
    common_food_words = {"pack", "count", "oz", "lb", "fat", "lean", "value", "ct", "g", "pound", "reduced", "fridge",
                         "original", "full", "half", "size", "brand"}
    stop_words = stop_words | common_food_words | set(removable_brand_names) | set(plural_brands)  # take the union of all sets
    for ingr in ingredients:
        ingr_lower = ingr
        ingr_lower = ingr_lower.replace(",", "")
        ingr_lower = ingr_lower.replace("%", "")
        ingr_lower = ingr_lower.replace("'", "")
        for brand in removable_brand_names:
            if brand in ingr_lower:
                ingr_lower = ingr_lower.replace(brand, "")
        tokenized_ingr = word_tokenize(ingr_lower)
        word = [w for w in tokenized_ingr if w not in stop_words and not has_numbers(w) and len(w) > 1]
        shortened_ingredients.append(" ".join(word))
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
    #options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    action = AC(driver)
    url = "https://shop.gianteagle.com/squirrel-hill/search?cat=48&page=2"
    driver.get(url)
    time.sleep(5)
    #driver.maximize_window() # makes the window full_screen
    wait = WebDriverWait(driver, 15) # wait at most 15 seconds for anything to load
    all_brands = giant_eagle_all_brands(driver, wait)
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
    first_item_of_prev_iter, first_item_of_next_iter = "", ""
    #driver.get_screenshot_as_file("screenshot2.png")

    counter = 0
    # counter is used to check how many iterations we've gotten
    # the same first element.
    while True:
        try:
            # find all product names on the page that load
            items = wait.until(EC.presence_of_all_elements_located((By.XPATH, '//div[@class="sc-fbAgdq bNmZPW"]')))
            # get the first product name that is in the list. the logic below is used
            # to check if we've hit the bottom of the page, and we keep getting
            # the same results
            first_item_of_next_iter = items[0].text
            if first_item_of_next_iter == first_item_of_prev_iter:
                counter += 1
                if counter > 100:
                    break
            else:
                counter = 0
            # this may add duplicates to our list, but we don't care
            for item in items:
                all_ingredients.append(item.text.lower())
        except Exception as e:
            # this program frequently gets stale exceptions in the try statement above
            # what this does, essentially, is it retries loading the elements that show up
            # while ONLY changing the count number. this problem is reduced if we implement
            # some forced waiting at the start of the while loop, e.g. time.sleep(3)
            #print("\n", "Throwed error on count", count, "\n", e)
            continue
        action.send_keys(Keys.PAGE_DOWN).send_keys(Keys.PAGE_DOWN).send_keys(Keys.PAGE_DOWN).perform()
        # part of the logic in checking if we've reached the bottom
        first_item_of_prev_iter = first_item_of_next_iter
    # removes all duplicates from the list, while maintaining the same
    # relative order of the items. there should be quite a lot, so this
    # is a necessary step
    all_ingredients = list(dict.fromkeys(all_ingredients))
    all_ingredients = giant_eagle_data_sanitation(all_ingredients, all_brands)
    ln = len(all_ingredients)
    print("There are", ln," ingredients")
    #print_ingredients(all_ingredients, 5, ln)
    # writes the results to a file. after all, we don't want to be rerunning this everytime a user makes a request
    # instead, we should be loading up the file and searching the results on here
    with open('ingredients_output2.txt', 'w') as f:
        for item in all_ingredients:
            # write each item on a new line
            f.write(f"{item}\n")
    driver.quit()

def check_giant_eagle_store(ingredient_list):
    ln = len(ingredient_list)
    res = [False] * ln
    with open('ingredients_output2.txt') as f:
        stocked_ingredients = f.read().splitlines()
    for i in range(ln):
        item = ingredient_list[i]
        (best_match, score) = process.extractOne(item, stocked_ingredients, scorer=fuzz.token_sort_ratio)
        if score > 85:
            res[i] = True
        print(score, best_match, "\n")
    return res

def check_trader_joe_store(ingredient_list):
    '''
    We don't bother with brands here, since Trader Joe does not stock any popular brands
    '''
    options = FirefoxOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Firefox(options=options)
    results = [False] * len(ingredient_list)
    url = "https://www.traderjoes.com/home/search?q=x&section=products&global=no"
    driver.get(url)
    wait = WebDriverWait(driver, 10)
    cookies_button = wait.until(EC.presence_of_element_located((By.XPATH,
                                                               '//button[@class="Button_button__3Me73 Button_button_variant_secondary__RwIii"]')))
    cookies_button.click()
    search_button = wait.until(EC.presence_of_element_located((By.XPATH,
                                                               '//button[@class="Button_button__3Me73 Search_action__2LXEg Button_button_variant_viewLink__2W82s"]')))
    search_button.click()  # this clicks the search button so that we can input our search query
    i = 0
    for ingredient in ingredient_list:
        text_box = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@type="text"]')))
        text_box.click()
        text_box.clear()
        text_box.send_keys(ingredient,
                                Keys.ENTER)  # enters the ingredient we want to look for, and then begins the search
        try:
            search_all_results_button = wait.until(
                EC.presence_of_element_located((By.XPATH, '//button[@type="submit"]')))
            search_all_results_button.click()
        except:
            print("No ingredients found", ingredient)
            i += 1
            continue
        try:
            all_products_button = wait.until(
                EC.presence_of_element_located((By.XPATH,
                                                '//button[@class="Button_button__3Me73 SearchResults_searchResults__sectionButton__2pbDw"]')))
            all_products_button.click()
        except Exception as e:
            print("Something went wrong 2", ingredient)
            print(e, "\n\n")
            i += 1
            continue
        try:
            element = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//a[@class="Link_link__1AZfr SearchResultCard_searchResultCard__titleLink__2nz6x"]')))
        except:
            print("Elements not found for ingredient", ingredient)
            i += 1
            continue
        page_results = driver.find_elements(By.XPATH,
                                            '//a[@class="Link_link__1AZfr SearchResultCard_searchResultCard__titleLink__2nz6x"]')  # finds all titles of each food item, as this is all we care about
        stocked_items = [item.text.lower() for item in page_results]
        stocked_items = ingredient_sanitize_data(stocked_items, [])
        (best_match, score) = process.extractOne(ingredient, stocked_items, scorer=fuzz.token_sort_ratio)
        if score > 70:
            results[i] = True
        print(score, best_match, "\n")
        i += 1
    driver.quit()
    # print(results)
    # print("Total time is ", end_time - start_time)
    return results

def ingredient_sanitize_data(stocked_items, all_brands):
    shortened_ingredients = []
    plural_brands = [brand + "s" for brand in all_brands]
    stop_words = set(stopwords.words('english'))
    common_food_words = {"pack", "count", "oz", "lb", "fat", "lean", "value", "ct", "g", "pound", "reduced", "fridge",
                         "original", "full", "half", "size", "brand"}
    stop_words = stop_words | common_food_words | set(all_brands) | set(
        plural_brands)  # take the union of all sets
    for ingr in stocked_items:
        ingr_lower = ingr
        ingr_lower = ingr_lower.replace(",", "")
        ingr_lower = ingr_lower.replace("%", "")
        ingr_lower = ingr_lower.replace("'", "")
        for brand in all_brands:
            if brand in ingr_lower:
                ingr_lower = ingr_lower.replace(brand, "")
        tokenized_ingr = word_tokenize(ingr_lower)
        word = [w for w in tokenized_ingr if w not in stop_words and not has_numbers(w) and len(w) > 1]
        shortened_ingredients.append(" ".join(word))
    ingredients = stocked_items + shortened_ingredients
    return ingredients
def check_all_stores(ingredient_list):
    #scrape_squirrel_giant_eagle()
    giant_eagle_results = check_giant_eagle_store(ingredient_list)
    aldis_results = scrape_squirrel_aldis(ingredient_list)
    print(giant_eagle_results)
    print(aldis_results)


#check_all_stores(ingredient_list)
# call the function to scrape Giant Eagle website
#scrape_squirrel_giant_eagle()
check_trader_joe_store(["bananas", "banana", "pringles", "teriyaki sauce", "general tso sauce"])
#check_giant_eagle_store(["sour cream and onion pringles", "cheez-its crackers"])
#print(fuzz.token_set_ratio("lemon cheesecake", "lemon"))
#check_giant_eagle_store(["banana", "pringles", "dark chocolate", "blurpies", "kosher apple pie", "apple pie", "giant eagle apple pie"])
