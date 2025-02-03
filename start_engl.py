import requests
import re
import os
from jinja2 import Environment, FileSystemLoader, Template
from fractions import Fraction
from urllib.parse import urlparse
import argparse


#api_url = "[YOUR_TANDOOR_HOST]/api"
#recipe_url = f"{api_url}/recipe"
#headers = {
#    "Authorization": "Bearer [YOUR_TANDOOR_TOKEN]"
#}

def extract_domain(url):
    if not url:
        return None
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    # Remove "www." Prefix
    domain = re.sub(r'^www\.', '', domain)
    return domain if domain else None

def fetch_recipe_data(recipe_id, recipe_url, headers):
    """Fetches recipe Data from API and extracts domain from source_url"""
    recipe_id_url = f"{recipe_url}/{recipe_id}/"
    response = requests.get(recipe_id_url, headers=headers)
    if response.status_code == 200:
        recipe_data = response.json()
        if 'source_url' in recipe_data and recipe_data['source_url']:
            extracted_domain = extract_domain(recipe_data['source_url'])
            recipe_data['source_domain'] = extracted_domain if extracted_domain else recipe_data['source_url']
        else:
            recipe_data['source_domain'] = None
        return recipe_data
    else:
        print(f"Recipe-ID {recipe_id} could not be found (Status: {response.status_code}).")
        return None

def download_recipe_image(recipe_data, recipe_name, pictures_dir):
    if 'image' in recipe_data and recipe_data['image']:
        image_url = recipe_data['image']
        image_response = requests.get(image_url)
        if image_response.status_code == 200:
            image_extension = os.path.splitext(image_url)[1]
            image_path = os.path.join(pictures_dir, f"{recipe_name}{image_extension}")
            with open(image_path, 'wb') as image_file:
                image_file.write(image_response.content)
            print(f"Picture for {recipe_name} downloaded successfully.")
        else:
            print(f"Picture could not be downloaded: {image_url}")
    else:
        print(f"No picture found for {recipe_name}.")

def decimal_to_nicefrac(value):
    try:
        value = float(value)
    except ValueError:
        return value
    if value.is_integer():
        return str(int(value))
    frac = Fraction(value).limit_denominator(8)
    if frac.numerator > frac.denominator:
        whole_number = frac.numerator // frac.denominator
        fraction_part = frac - whole_number
        return f"{whole_number}\\nicefrac{{{fraction_part.numerator}}}{{{fraction_part.denominator}}}"
    else:
        return f"\\nicefrac{{{frac.numerator}}}{{{frac.denominator}}}"

def replace_celsius(value):
    return value.replace("°C", r"\textcelcius")

def replace_min_space(value):
    if isinstance(value, str):
        value = re.sub(r'(\d+)\s+Min\.', r'\1~Min.', value)
        value = re.sub(r'(\d+)\s+min\.', r'\1~min.', value)
        value = re.sub(r'(\d+)\s+Minuten', r'\1~Minuten', value)
    return value

def replace_percent(value):
    return re.sub(r'(\d)%', r'\1\\%', value)

def replace_numbers_with_step(text):
    text = re.sub(r'\b\d+\.\s', r'\\step ', text)
    return text

def escape_ampersand(value):
    return value.replace(r"&", r"\&")

def recipe_to_tex(recipe_data, output_dir, template, pictures_dir):
    """ 
    Creates a LaTeX file from a recipe data object

    Args:
        recipe_data: A dictionary containing the recipe data
        output_dir: The directory where the LaTeX file will be saved
        template: The Jinja2 template to use for rendering the LaTeX content
        pictures_dir: The directory where the recipe images will be saved
    """
    recipe_name = recipe_data['name'].replace("/", "-")
    output_path = os.path.join(output_dir, f"{recipe_name}.tex")
    try:
        latex_content = template.render(recipe=recipe_data)
    except Exception as e:
        print(f"Error rendering template for {recipe_name}: {e}")
        return
    with open(output_path, 'w', encoding="utf-8") as file:
        file.write(latex_content)
    download_recipe_image(recipe_data, recipe_name, pictures_dir)
    print(f"{recipe_name}.tex exported successfully.")

def main(tandoor_url, tandoor_token, recipe_id=None):

    recipe_url = f"{tandoor_url}/api/recipe"
    headers = {
        "Authorization": f"Bearer {tandoor_token}"
    }
    env = Environment(
        loader=FileSystemLoader("templates"),
        block_start_string="<<%",
        block_end_string="%>>",
        variable_start_string="<<",
        variable_end_string=">>",
        comment_start_string="<<#",
        comment_end_string="#>>"
    )

    env.filters['replace_celsius'] = replace_celsius
    env.filters['replace_min_space'] = replace_min_space
    env.filters['decimal_to_nicefrac'] = decimal_to_nicefrac
    env.filters['replace_percent'] = replace_percent
    env.filters['replace_numbers_with_step'] = replace_numbers_with_step
    env.filters['escape_ampersand'] = escape_ampersand

    print(recipe_url)
    response = requests.get(recipe_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        total_count = data['count']
        print(f"{total_count} Recipes found.")
    else:
        raise Exception(f"Error: {response.status_code} - {response.text}")

    template = env.get_template('xcookybooky-josh.txt')

    output_dir = "exported_recipes"
    os.makedirs(output_dir, exist_ok=True)

    pictures_dir = os.path.join(output_dir, "Pictures")
    os.makedirs(pictures_dir, exist_ok=True)

    if recipe_id is None:
        for recipe in data['results']:
            recipe_id = recipe['id']
            recipe_data = fetch_recipe_data(recipe_id, recipe_url, headers)
            recipe_to_tex(recipe_data, output_dir, template, pictures_dir)
    else:
        recipe_data = fetch_recipe_data(recipe_id, recipe_url, headers, pictures_dir)
        recipe_to_tex(recipe_data, output_dir, template)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Recipes from Tandoor to LaTeX")

    parser.add_argument("--tandoor-url", help="URL of the Tandoor API")
    parser.add_argument("--api-token", help="API Token for Tandoor")
    parser.add_argument("--recipe-id", help="ID of the Recipe to export, if not provided all recipes will be exported", default=None)

    args = parser.parse_args()
    main(args.tandoor_url, args.api_token, args.recipe_id)