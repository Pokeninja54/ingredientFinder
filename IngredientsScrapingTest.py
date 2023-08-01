
'''
Project: Given a list of ingredients, find which stores nearby sell all of those ingredients. Currently
focusing on supermarkets, but could do drugstores as well if this works out

Accomplishes this by finding the search box for each website, searching for each ingredient in the ingredient list, and
then scraping and processing the results of the individual searches. Currently supports multiprocessing to run the
webscrapers in parallel.

When processing the results, I am using fuzzy matching, as seen with thefuzz library. More specifically, I am using
the token sort function, as this has had the best result so far, though it is easy to play around with this and
try other functions by replacing the scorer attribute in the "check_ingredient_in_page_results" function. There
is room for improvement here certainly.

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

Currently supports Aldis, Giant Eagle, and Trader Joe's

'''

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from thefuzz import fuzz, process
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from multiprocessing import Process, Queue
import time

SCORE_THRESHOLD = 70 # define this macro so that we can adjust the scoring threshold for each website.
# unlikely that we want an individual threshold per website?
WEBDRIVER_WAIT_THRESHOLD = 5 # how long any webdriver should wait for before giving up

def has_numbers(inputString):
    return any(char.isdigit() for char in inputString)

def driver_startup():
    '''
    Returns: Driver with the correct options startup. This is because I use the same driver for every
    website, may as well shorten it. Currently just runs it in headless mode with a maximized window.
    Uses Firefox because many websites tend to block Chrome.
    '''
    options = FirefoxOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    return driver

def check_ingredient_in_page_results(ingredient, page_results, all_brands, results, i):
    '''
    This takes in the scraped results from a website, and sanitizes the data to make comparisons easier.
    It then looks for the closest item in the sanitized data compared to our desired ingredient, and produces
    some score. If this surpasses the score threshold, then our item is in the store with high probability.
    '''
    stocked_items = [item.text.lower() for item in page_results]
    stocked_items = ingredient_sanitize_data(stocked_items, all_brands)
    (best_match, score) = process.extractOne(ingredient, stocked_items, scorer=fuzz.token_sort_ratio)
    if score > SCORE_THRESHOLD:
        results[i] = True
    #print(score, best_match, "\n")

def print_ingredients(ingredients, line_width):
    '''
    Allows me to print the scraped results in a somewhat neat manner.
    This is no longer being used.
    '''
    length = len(ingredients)
    count = 0
    while count < length:
        for j in range(line_width):
            if count + j < length:
                print(ingredients[count + j])
        print("\n")
        count += line_width

def aldis_all_brands(wait):
    '''
    This function clicks on the Brands button on the Aldi's website
    and finds all of the brand names contained there.
    '''
    elements = wait.until(EC.visibility_of_all_elements_located((By.XPATH, '//button[@class="e-1ff8o8k"]')))
    '''
    There are multiple elements with this xpath, and there is no easy way to find the Brands button (at least
    not with the XPATH, could try another method if I want to remove the for loop below?). Thus, we check
    each element found to see if it is the correct one.
    '''
    for i in range(len(elements)):
        elem = elements[i]
        button_name = elem.find_element(By.XPATH, ".//span").text
        if button_name == "Brands":
            elem.click()
            break
        if i == len(elements) - 1:
            return []
    all_brand_names = wait.until(EC.presence_of_all_elements_located((By.XPATH, '//label[@class="e-1rv1880"]')))
    result = []
    for brand in all_brand_names:
        text = brand.text
        if text != "":
            result.append(text.lower())
    print("All the brands are", result)
    return result

def giant_eagle_all_brands(wait):
    '''
    This function clicks on the Brands button on the Giant Eagle website
    and finds all of the brand names contained there. It removes the count of each brand, since
    we only want the names.
    '''
    element = wait.until(EC.visibility_of_element_located((By.XPATH, '//button[@aria-label="Brand: "]')))
    element.click()
    time.sleep(1) # necessary, as otherwise the wait call below might fail. unclear why though, since it waits for 5 seconds, which should be plenty of time
    all_brand_names = wait.until(EC.presence_of_all_elements_located((By.XPATH, '//div[@class="sc-cgHAeM jVHret"]'))) # '//div[@class="sc-cgHAeM jVHret"]'
    result = []
    for brand in all_brand_names:
        text = brand.text
        first_parentheses_idx = text.find('(')
        # the giant eagle website stores the count of each brand in the form "giant eagle (14)", which we don't care for
        if first_parentheses_idx != -1:
            text = text[:first_parentheses_idx]
        text = text.replace("'", "")
        if text != "":
            result.append(text.lower())
    element.click()
    print("All the brands are", result)
    return result

def check_aldis_store(ingredient_list, queue):
    '''
    Returns: A list indicating which ingredients were found on the online website.
    Ingredient list is a list of ingredients that we are searching for, and queue
    is used to store the results safely, as this function is a spawned process,
    so returning the results is a bit finnicky otherwise
    '''
    driver = driver_startup()
    results = [False] * len(ingredient_list)
    url = "https://shop.aldi.us/store/aldi/storefront/?current_zip_code=15206&utm_source=yext&utm_medium=local&utm_campaign=brand&utm_content=shopnow_storepage"
    driver.get(url)
    wait = WebDriverWait(driver, WEBDRIVER_WAIT_THRESHOLD)
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
            all_brands = aldis_all_brands(wait)
        except:
            print("No ALDIS brands button for ingredient", ingredient)
        page_results = driver.find_elements(By.XPATH, '//span[@class="e-8zabzc"]') # finds all titles of each food item, as this is all we care about
        check_ingredient_in_page_results(ingredient, page_results, all_brands, results, i)
        i += 1
    driver.quit()
    queue.put(results)
    return results

def check_giant_eagle_store(ingredient_list, queue):
    '''
    Same as ALDI's function, but for Giant Eagle
    '''
    driver = driver_startup()
    results = [False] * len(ingredient_list)
    url = "https://shop.gianteagle.com/squirrel-hill/search?page=2"
    driver.get(url)
    wait = WebDriverWait(driver, WEBDRIVER_WAIT_THRESHOLD)
    search_button = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@aria-label="Search"]')))
    i = 0
    for ingredient in ingredient_list:
        search_button.click()  # this clicks the search button so that we can input our search query
        search_button.clear()  # this clears anything in the search box
        search_button.send_keys(ingredient,
                                Keys.ENTER)  # enters the ingredient we want to look for, and then begins the search
        try:
            item = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@class="sc-fbAgdq bNmZPW"]')))
        except:
            print("Elements not found for ingredient", ingredient)
            i += 1
            continue
        all_brands = []
        try:
            all_brands = giant_eagle_all_brands(wait)
        except:
            print("No Giant Eagle brands button for ingredient", ingredient)
        page_results = driver.find_elements(By.XPATH,
                                            '//div[@class="sc-fbAgdq bNmZPW"]')  # finds all titles of each food item, as this is all we care about
        check_ingredient_in_page_results(ingredient, page_results, all_brands, results, i)
        i += 1
    driver.quit()
    queue.put(results)
    return results

def check_trader_joe_store(ingredient_list, queue):
    '''
    Same as ALDI's function, but for Trader Joe's
    '''
    driver = driver_startup()
    results = [False] * len(ingredient_list)
    url = "https://www.traderjoes.com/home/search?q=x&section=products&global=no"
    driver.get(url)
    wait = WebDriverWait(driver, WEBDRIVER_WAIT_THRESHOLD)
    cookies_button = wait.until(EC.presence_of_element_located((By.XPATH,
                                                               '//button[@class="Button_button__3Me73 Button_button_variant_secondary__RwIii"]'))) # was getting weird exception with the cookies button, need to clear it
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
            print("No ingredients found for ingredient: ", ingredient)
            i += 1
            continue
        try:
            all_products_button = wait.until(
                EC.presence_of_element_located((By.XPATH,
                                                '//button[@class="Button_button__3Me73 SearchResults_searchResults__sectionButton__2pbDw"]')))
            all_products_button.click()
        except:
            print("All products button missing for ingredient: ", ingredient)
            i += 1
            continue
        try:
            element = wait.until(EC.presence_of_element_located(
                (By.XPATH, '//a[@class="Link_link__1AZfr SearchResultCard_searchResultCard__titleLink__2nz6x"]')))
        except:
            print("Elements not found when they should exist for ingredient: ", ingredient)
            i += 1
            continue
        page_results = driver.find_elements(By.XPATH,
                                            '//a[@class="Link_link__1AZfr SearchResultCard_searchResultCard__titleLink__2nz6x"]')  # finds all titles of each food item, as this is all we care about
        check_ingredient_in_page_results(ingredient, page_results, [], results, i)
        # note that we pass in the empty list for the brands. this is unique to trader joes, as they don't stock popular brands
        i += 1
    driver.quit()
    queue.put(results)
    return results

def ingredient_sanitize_data(stocked_items, all_brands):
    '''
    This is a function that is used purely because we are using fuzzy matching for our check
    for ingredients in the scraped data. As we use the token sort ratio, we don't want words
    that are meaningless devaluing the ratio, so we remove certain tokens from each stocked item
    to make the comparison better. This includes brand names, amounts of each item, and other
    more generic terms. We only append this to our original list in case the user does want
    to look for these specific terms/brands
    '''
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
def check_all_stores(ingredient_list, list_of_store_fns):
    '''
    Driver function that implements multiprocessing to webscrape each supermarket website
    in parallel. If there are n websites, this is a speedup by n times roughly compared to sequential
    webscraping.
    '''
    start_time = time.time()
    q = Queue()
    results = []
    processes = []
    for store_fn in list_of_store_fns:
        p = Process(target=store_fn, args=(ingredient_list,q,))
        processes.append(p)
        p.start()
    for _ in processes:
        results.append(q.get())
    for process in processes:
        process.join()
    print(results)
    end_time = time.time()
    print("Total time taken was ", end_time - start_time)

if __name__ == '__main__':
    ingredient_list = ["bananas", "banana", "pringles", "teriyaki sauce", "general tso sauce"]
    check_all_stores(ingredient_list, [check_trader_joe_store, check_giant_eagle_store, check_aldis_store])