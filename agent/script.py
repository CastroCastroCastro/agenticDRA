'''
Script for streaming in json and putting into the rpc handler
Obtain GB and the number of cores from machines.json
Maintain a global lock to avoid multiple agents from spinning up on the same machine or modifying the same machine at the same time
Spin up an agent and connect the agent to the machine via RPC
'''

from ast import List
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




"""
OVERALL THE AGENT SHOULD RUN THE SCRIPT
TASK1: Read the machines.json file and get the machine details --> COMPLETED
Task2: CREATE THE RPC METHOD INVOCTION THAT WILL BE USED TO CONNECT TO THE MACHINE 
"""
class Script:
    def __init__(self):
        self.machines = self._read_machines()

    def _read_machines(self):
        with open('machines.json', 'r') as f:
            data = json.load(f)
        # Support both: single dict of machines, or JSON Lines (list of objects)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list) and data:
            return data
        raise ValueError("No machines found in the file")

    def _get_available_machines(self):
        return [machine for machine in self.machines if machine['memory_gb'] > 0]
    
    

    
    def _create_rpc_method(ip: str, ports: List[int]):
        """
        This mehtod will create the rpc connection to the machine
        The agent will invoke this method to connect to the machine after selecting the best available machine
        
        """
        
        pass
    
    






        