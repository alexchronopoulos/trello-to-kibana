# Trello to Kibana
## Description
This project provies the means to visualize Trello Card data in Kibana.

This is a free and open source alternative to the Trello Premium Dashboard View.
## Requirements
- Python 3.9+
  - [PyTrello](https://pypi.org/project/py-trello/)
  - [Elasticserch-Py](https://elasticsearch-py.readthedocs.io/en/v8.4.2/)
  - [Requests](https://pypi.org/project/requests/)
  - [python-dotenv](https://pypi.org/project/python-dotenv/)
- An [API Key and Token](http://www.trello.org/help.html) for Trello authentication
- An [API Key](https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-create-api-key.html) for Elastic authentication
## Quickstart

1. Clone the repository
2. Create `config.ini` file using `config.ini_template` as a base
3. Activate Python venv `source bin/activate`
4. Install requirements `pip3 install -r requirements.txt`
5. Run `python3 trello_to_elastic.py`

Assuming all goes well this will perform the following:
- Pull data for all Cards on Trello Board
- Ship data to Elastic Indices `trello-open` and `trello-closed`
- Create Kibana Index Pattern and Dashboard `Trello`


