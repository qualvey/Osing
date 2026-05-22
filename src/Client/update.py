#get userdata and user_dir
from .ConfigEngine import ConfigGenerator

class ConfigUpdater():
    def __init__(self, linux_template: dict, ios_souce_config: dict,users: list):
        self.base_data = linux_template
        self.users = users
        self.linux_config_path = ""
        self.ios_template = ios_souce_config
        
    def update(self):
        for u in self.users:
            configGenerator = ConfigGenerator(self.base_data,self.ios_template, u )
            configGenerator.run()
