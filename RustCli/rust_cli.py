from push_receiver.push_receiver import listen, gcm_register, fcm_register
from selenium.webdriver.chrome.service import Service
from flask import Flask, render_template, request
from chromedriver_py import binary_path
from selenium import webdriver
from uuid import uuid4
import time, requests, json, urllib3, threading, sys, logging

# Dealing with hiding the messages :)
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


class RustCli:

    def __init__(self) -> None:
        self.token = ""
        self.uuid = uuid4()


    def getConfigFile(self):
        return "rustplus.py.config.json"


    def readConfig(self, file):
        try:
            with open(file) as fp:
                return json.load(fp)
        except:
            return {}


    def updateConfig(self, file, data):
        with open(file, "w") as outputFile:
            json.dump(data, outputFile, indent=4, sort_keys=True)


    def getExpoPushToken(self, credentials):

        response = requests.post("https://exp.host/--/api/v2/push/getExpoPushToken", data={
            "deviceId" : self.uuid,
            "experienceId": '@facepunch/RustCompanion',
            "appId": 'com.facepunch.rust.companion',
            "deviceToken": credentials["fcm"]["token"],
            "type": 'fcm',
            "development": False
        })

        return response.json()["data"]["expoPushToken"]


    def registerWithRustPlus(self, authToken, expoPushToken):
            
        encoded_body = json.dumps({
                "AuthToken": authToken,
                "DeviceId": 'rustplus.js',
                "PushKind": 0,
                "PushToken": expoPushToken,
            }).encode('utf-8')

        return urllib3.PoolManager().request('POST', 'https://companion-rust.facepunch.com:443/api/push/register',
                        headers={'Content-Type': 'application/json'},
                        body=encoded_body)

    
    def clientView(self):

        options = webdriver.ChromeOptions()
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-site-isolation-trials")

        service = Service(binary_path)
        driver = webdriver.Chrome(service=service, options=options, service_log_path='/dev/null')
        driver.get("http://localhost:3000")
        
        while True:
            try:
                if str(driver.current_url).startswith("http://localhost:3000/callback"):
                    driver.close()
                    break
                time.sleep(1)
            except Exception:
                return
    

    def linkSteamWithRustPlus(self):

        thread = threading.Thread(target=self.clientView)
        thread.start()
        
        app = Flask(__name__)

        @app.route('/')
        def main():
            return render_template("pair.html")

        @app.route('/callback')
        def callback():
            self.token = request.args["token"]
            try:
                request.environ.get('werkzeug.server.shutdown')()
            except:
                pass

            return "All Done!"

        app.run(port = 3000)

        return self.token

    def registerWithFCM(self, sender_id):

        appId = "wp:receiver.push.com#{}".format(self.uuid)
        subscription = gcm_register(appId=appId, retries=50)
        fcm = fcm_register(sender_id=sender_id, token=subscription["token"])
        res = {"gcm": subscription}
        res.update(fcm)
        return res


    def fcmRegister(self):

        print("Registering with FCM")
        fcmCredentials = self.registerWithFCM(976529667804)

        print("Registered with FCM")

        print("Fetching Expo Push Token")
        try:
            expoPushToken = self.getExpoPushToken(fcmCredentials)
        except Exception:
                print("Failed to fetch Expo Push Token")
                quit()

        # show expo push token to user
        print("Successfully fetched Expo Push Token")
        print("Expo Push Token: " + expoPushToken)

        # tell user to link steam with rust+ through Google Chrome
        print("Google Chrome is launching so you can link your Steam account with Rust+")
        rustplusAuthToken = self.linkSteamWithRustPlus()

        # show rust+ auth token to user
        print("Successfully linked Steam account with Rust+")
        print("Rust+ AuthToken: " + rustplusAuthToken)

        print("Registering with Rust Companion API")
        try:
            self.registerWithRustPlus(rustplusAuthToken, expoPushToken)
        except Exception:
            print("Failed to register with Rust Companion API")
            quit()
        print("Successfully registered with Rust Companion API.")

        # save to config
        configFile = self.getConfigFile()
        self.updateConfig(configFile, {
            "fcm_credentials": fcmCredentials,
            "expo_push_token": expoPushToken,
            "rustplus_auth_token": rustplusAuthToken,
        })

        print("FCM, Expo and Rust+ auth tokens have been saved to " + configFile)


    def on_notification(self, obj, notification, data_message):

        print(json.dumps(json.loads(notification["data"]["body"]), indent=4, sort_keys=True))


    def fcmListen(self):

        with open(self.getConfigFile(), "r") as file:
            credentials = json.load(file)

        print("Listening...")

        listen(credentials=credentials["fcm_credentials"], callback=self.on_notification)

    

if __name__ == "__main__":

    cli = RustCli()

    
    cli.fcmRegister()
    cli.fcmListen()