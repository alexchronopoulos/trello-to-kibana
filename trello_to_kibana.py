import configparser
import logging
import os
import requests
from datetime import datetime
from datetime import timezone
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from pprint import pprint
from trello import TrelloClient


def process_last_activity_seconds(card):
    """Processes duration in seconds
    between now and card last activity.
    This is done to provide an interesting
    metric on Kibana Dashboards."""
    if card.date_last_activity:
        return abs(
            (datetime.now(timezone.utc) - card.date_last_activity).total_seconds()
        )


def process_age(card):
    """Processes duration in seconds
    between when card was created and
    current time. This is done to provide
    an interesting metric on Kibana Dashboards."""
    return abs((datetime.now(timezone.utc) - card.created_date).total_seconds())


def process_list_id(card):
    """Processes List Name for
    active Cards or returns Archive
    for closed Cards. This is done to
    clearly indicate archived Cards on
    Kibana Dashboards."""
    if card.closed:
        return "Archive"
    else:
        return lists[card.list_id]


def process_timestamp_field(card):
    """Returns date of last activity
    for closed Cards and date created
    for open Cards. This is done so
    open and closed Cards can be visualized
    on the same Kibana Dashboard."""
    if card.closed:
        return datetime.isoformat(card.date_last_activity)
    else:
        return datetime.isoformat(card.created_date)


def process_time_active(card):
    """Returns difference between
    when card was created and last
    activity. This is intended to
    capture how long it took to
    complete a closed card."""
    return abs((card.date_last_activity - card.created_date).total_seconds())


def process_card_status(card):
    """Returns a string defining
    the ultimate status of a Card.
    This is done to more clearly display
    Open/Closed Cards in Kibana. Also,
    if a Card is Archived as part of a List
    Archive action the Closed status never
    gets set to True resulting in skewed results.
    This function will mark any Card on a Board's
    Closed Lists as Closed"""
    if card.closed:
        return "Closed"
    elif closedLists.get(card.idList):
        return "Closed"
    else:
        return "Open"


def parse_comment_datetime(dateString):
    """Helper function to return a datetime
    object given a timestamp associated with
    a Card comment."""
    return datetime.strptime(dateString, "%Y-%m-%dT%H:%M:%S.%fZ")


def process_comment_times(card):
    """Returns time since first
    and last comment on a Card."""
    if card.comments:
        timeToFirstComment = abs(
            (
                parse_comment_datetime(card.comments[0]["date"]) - datetime.now()
            ).total_seconds()
        )
        timeSinceLastComment = abs(
            (
                parse_comment_datetime(card.comments[-1]["date"]) - datetime.now()
            ).total_seconds()
        )
        return {
            "timeToFirstComment": timeToFirstComment,
            "timeSinceLastComment": timeSinceLastComment,
        }
    else:
        return {}


def get_last_comment(card):
    """Returns the text from the
    latest comment on a Card."""
    if card.comments:
        return card.comments[-1]["data"]["text"]


def process_cards(cards):
    """Receives a list of Cards and
    yields relevant data for ingesting
    into Elastic"""
    for card in cards:
        yield {
            "_id": card.id,
            "@timestamp": process_timestamp_field(card),
            "name": card.name,
            "list": process_list_id(card),
            "closed": card.closed,
            "labels": [label.name for label in card.labels],
            "created_date": datetime.isoformat(card.created_date),
            "date_last_activity": datetime.isoformat(card.date_last_activity),
            "members": [members[memberId] for memberId in card.idMembers],
            "shortUrl": card.shortUrl,
            "lastActivitySeconds": process_last_activity_seconds(card),
            "age": process_age(card),
            "timeActiveSeconds": process_time_active(card),
            "status": process_card_status(card),
            "numComments": len(card.comments),
            "timeToFirstComment": process_comment_times(card).get("timeToFirstComment"),
            "timeSinceLastComment": process_comment_times(card).get(
                "timeSinceLastComment"
            ),
            "lastComment": get_last_comment(card),
        }


def export_kibana_objects(baseApiUrl, headers):
    payload = {
        "objects": [
            {"type": "dashboard", "id": "ead49010-3ec2-11ed-8d8c-37728a319e21"},
            {"type": "index-pattern", "id": "14ed31a0-3ec2-11ed-8d8c-37728a319e21"},
        ],
        "excludeExportDetails": "true",
    }
    r = requests.post(
        headers=headers, url=f"{baseApiUrl}/saved_objects/_export", json=payload
    )
    r.raise_for_status()
    with open("kibana/KibanaExport.ndjson", "w") as outfile:
        outfile.write(r.text)


def import_kibana_objects(baseApiUrl, headers):
    files = {"file": open("kibana/KibanaExport.ndjson", "rb")}
    r = requests.post(
        headers=headers,
        url=f"{baseApiUrl}/saved_objects/_import?overwrite=true",
        files=files,
    )
    return r.content


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logging.info("Reading .env file")
    load_dotenv()

    logging.info("Reading configuration file config.ini")
    config = configparser.ConfigParser()
    config.read("config.ini")

    elasticApiKey = config["elastic"]["ApiKey"] or os.environ.get("ELASTIC_API_KEY")
    trelloApiKey = config["trello"]["ApiKey"] or os.environ.get("TRELLO_API_KEY")
    trelloApiSecret = config["trello"]["ApiSecret"] or os.environ.get(
        "TRELLO_API_SECRET"
    )
    trelloToken = config["trello"]["Token"] or os.environ.get("TRELLO_TOKEN")
    trelloBoard = config["trello"]["Board"] or os.environ.get("TRELLO_BOARD")

    if config["actions"].getboolean("SendDataToElastic"):
        logging.info("Connecting to Elasticsearch host %s", config["elastic"]["host"])
        es = Elasticsearch(config["elastic"]["Host"], api_key=elasticApiKey)

        logging.info(
            "Connecting to Trello using API key %s", config["trello"]["ApiKey"]
        )
        client = TrelloClient(
            api_key=trelloApiKey, api_secret=trelloApiSecret, token=trelloToken
        )

        logging.info("Grabbing Trello Board %s", trelloBoard)
        board = client.get_board(trelloBoard)

        logging.info("Grabbing all Trello Members on Trello Board %s", board.name)
        members = {member.id: member.username for member in board.get_members()}
        logging.info("Found %s Members", len(members))

        logging.info("Grabbing all Lists on Trello Board %s", board.name)
        lists = {item.id: item.name for item in board.all_lists()}
        closedLists = {item.id: item.name for item in board.closed_lists()}
        logging.info("Found %s Lists", len(lists))

        logging.info("Grabbing all open Cards on Trello Board %s", board.name)
        openCards = board.open_cards()
        logging.info("Found %s open Cards", len(openCards))

        logging.info("Grabbing all closed Cards on Trello Board %s", board.name)
        closedCards = board.closed_cards()
        logging.info("Found %s closed Cards", len(closedCards))

        logging.info(
            "Sending closed Card data to Elasticsearch Index %s",
            config["elastic"]["ClosedCardsIndex"],
        )
        bulk(
            client=es,
            index=config["elastic"]["ClosedCardsIndex"],
            actions=process_cards(closedCards),
        )

        logging.info(
            "Sending open Card data to Elasticsearch Index %s",
            config["elastic"]["OpenCardsIndex"],
        )
        bulk(
            client=es,
            index=config["elastic"]["openCardsIndex"],
            actions=process_cards(openCards),
        )

    if config["actions"].getboolean("ExportKibanaObjects"):
        logging.info(
            "Setting headers for requests to Kibana API %s",
            config["elastic"]["KibanaBaseApiUrl"],
        )
        headers = {"kbn-xsrf": "true", "Authorization": f"ApiKey {elasticApiKey}"}
        logging.info("Exporting objects from Kibana")
        export_kibana_objects(config["elastic"]["KibanaBaseApiUrl"], headers)

    if config["actions"].getboolean("ImportKibanaObjects"):
        logging.info(
            f"Setting headers for requests to Kibana API %s",
            config["elastic"]["KibanaBaseApiUrl"],
        )
        headers = {"kbn-xsrf": "true", "Authorization": f"ApiKey {elasticApiKey}"}
        logging.info("Importing objects to Kibana")
        import_kibana_objects(config["elastic"]["KibanaBaseApiUrl"], headers)
