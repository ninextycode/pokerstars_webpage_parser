import requests
import bs4
import json


def get_game_json(url):
    response = requests.get(url)
    response.raise_for_status()

    parser = bs4.BeautifulSoup(response.text, "lxml")
    data_tag = parser.find("script", type="application/json")
    game_data = json.loads(data_tag.text)
    
    return game_data
     
def get_game_id(url):
    game_id = [p for p in url.split("/") if len(p) > 0][-1]
    return game_id