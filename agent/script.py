'''
Script for streaming in json and putting into the rpc handler
Obtain GB and the number of cores from machines.json
Maintain a global lock to avoid multiple agents from spinning up on the same machine or modifying the same machine at the same time
Spin up an agent and connect the agent to the machine via RPC
'''

import json
import threading
import time
import random
import string
import requests
import socket
import subprocess
import os
import sys
import logging
import logging.handlers