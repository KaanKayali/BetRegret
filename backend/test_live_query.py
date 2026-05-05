import os
from dotenv import load_dotenv
load_dotenv()
import soccer_server

print('FOOTBALL_DATA_API_KEY set:', os.getenv('FOOTBALL_DATA_API_KEY') is not None)
print('Result:', soccer_server.get_live_match_for_team('Bayern Munich'))
