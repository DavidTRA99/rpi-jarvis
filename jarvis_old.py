import RPi.GPIO as GPIO
import time
from threading import Thread
import subprocess
import getpass
import random
import os
from datetime import datetime

from lib_oled96 import ssd1306
from PIL import ImageFont, ImageDraw, Image
from smbus import SMBus

from LibWeather import WeatherSystem

from speech_recognition import Recognizer,Microphone,AudioFile
import wikipedia

user = 'david';
render_mode = 'time';
temp_text = None;
temp_text_ticks = 0;
current_time = datetime.now();

weather = None;
weathersystem = WeatherSystem();

wikipedia.set_lang('de');

i2cbus = SMBus(1);
oled = ssd1306(i2cbus);
font = ImageFont.load_default();
large_font = ImageFont.truetype('FreeSans.ttf', 16);
medium_font = ImageFont.truetype('FreeSans.ttf', 14);

def render():
    oled.canvas.rectangle((0,0,oled.width,oled.height), fill=0, outline=0);
    oled.canvas.text((0, 0), user + " @ linux  " + str(sensors.internaltemp) + "°C", fill=1, font=font);
    oled.canvas.line((0, 10, oled.width, 10), fill=1);
    if render_mode == 'time':
        oled.canvas.text((5, 15), str(current_time.hour) + ':' + str(current_time.minute) + ':' + str(current_time.second), fill=1, font=large_font);
        oled.canvas.text((5, 30), str(current_time.day) + '.' + str(current_time.month) + '.' + str(current_time.year), fill=1, font=large_font);
    elif render_mode == 'weather':
        oled.canvas.text((5, 15), str(weather['temperature']) + '°C', fill=1, font=font);
        oled.canvas.text((5, 23), str(weather['humidity']) + '% Luftfeuchtigkeit', fill=1, font=font);
        oled.canvas.text((5, 31), str(weather['wind']) + 'km/h Wind', fill=1, font=font);
        oled.canvas.text((5, 39), str(weather['clouds']) + '% Wolken', fill=1, font=font); 
    if temp_text != None:
        global temp_text,temp_text_ticks;
        oled.canvas.text((5, 50), ">> " + temp_text, fill=1, font=font);
        temp_text_ticks += 1;
        if temp_text_ticks>10:
            temp_text = None;
    oled.display();

def setAlert(pString):
    global temp_text,temp_text_ticks;
    temp_text = pString;
    temp_text_ticks = 0;

GPIO.setmode(GPIO.BOARD);

class GPIOInOut:
    def __init__(self, pin):
        self.pin = pin;
        GPIO.setup(pin, GPIO.OUT);

    def setOn(self, status):
        GPIO.output(self.pin, status);

    def timedOn(self, wait):
        self.setOn(True);
        time.sleep(wait);
        self.setOn(False);

buzzer = GPIOInOut(16);
buzzer.timedOn(0.2);


class SensorDataReceiver(Thread):
    def __init__(self):
        Thread.__init__(self, daemon=True);
        self.internaltemp = 0;

    def getInternalTemp(self):
        heat = subprocess.check_output(['vcgencmd', 'measure_temp']).decode();
        heat = heat[5:len(heat)-3];
        return heat;

    def run(self):
        global current_time;
        while True:
            self.internaltemp = self.getInternalTemp();
            current_time = datetime.now();            


sensors = SensorDataReceiver();
sensors.start();


class AnswerBot:

    def __init__(self, pData):
        self.data = [];
        with open(pData) as file:
            for line in file:
                line = line.replace('\n', '');
                split = line.split(':');
                if(len(split)<2):
                    continue;
                possibilities = split[0].split('|');
                answers = split[1].split("|");
                for entry in possibilities:
                    if(len(split)==2):
                        self.data.append([entry.split(','), answers]);
                    else:
                        self.data.append([entry.split(','), answers, split[2]]);
            file.close();
    def find_answer(self, pMessage):
        pMessage = pMessage.lower();
        for entry in self.data:
            is_valid = True;
            for keyword in entry[0]:
                if not keyword in pMessage:
                    is_valid = False;
                    break;
            if is_valid:
                if(len(entry)==2):
                    return random.choice(entry[1]),;
                else:
                    return random.choice(entry[1]), entry[2];
        return None,;

def exit(shutdown):
    oled.onoff(0);
    oled.cls();
    GPIO.cleanup();
    if shutdown:
        say('Das System wird ausgeschaltet.');
        os.system('sudo shutdown -h now');
    else:
        say('Das System wird neugestartet.');
        os.system('sudo reboot');
def say(pString):
        os.system('pico2wave --lang=de-DE --wave=/tmp/voiceout.wav "' + pString + '"');
        os.system('aplay /tmp/voiceout.wav');
        os.system('rm /tmp/voiceout.wav');
class SpeechRecognition(Thread):
    def __init__(self):
        Thread.__init__(self, daemon=True);
        self.rec = Recognizer();
        self.rec.energy_threshold=110;
        self.rec.pause_threshold=0.5;
        self.rec.operation_timeout=5;
        self.mic = Microphone(device_index = 2);
        self.answer = AnswerBot('de.txt');
    def command(self, command, said):
        global render_mode;
        command = command.split(" ");
        if command[0]=='time':
            render_mode = 'time';
            yield str(current_time.hour) + "Uhr und " + str(current_time.minute) + " minuten.";
        elif command[0]=='shutdown':
            exit(True);
        elif command[0]=='restart':
            exit(False); 
        elif command[0]=='wiki':
            search = said.lower().split(command[1].replace('_', ' '))[1].lower();
            setAlert('Suche: "' + search + '"');
            say("Suche nach " + search);
            result = wikipedia.summary(search);
            split = result.split('.');
            if len(split)>4:
                result = '';
                for i in range(0,4):
                    result += split[i] + '.';
            yield result;
        elif command[0]=='weather':
            global weather;
            if command[1] == 'today':
                yield "Hier ist die aktuelle Wetterlage.";
                weather = weathersystem.getCurrentWeather();
            elif command[1] == 'tomorrow':
                yield "Hier ist die vorrausichtliche Wetterlage.";
                weather = weathersystem.getWeatherTomorrow();
            render_mode = 'weather';
            yield 'Temperatur: ' + str(weather['temperature']) + '°C';
            yield 'Luftfeuchtigkeit: ' + str(weather['humidity']) + '%';
            yield 'Wind: ' + str(weather['wind']) + 'km/h';
            yield 'Bewölkung: ' + str(weather['clouds']) + '%';                
    def out(self, pMessage):
        setAlert('"' + pMessage + '"');
        print("Heard: " + pMessage);
        response = self.answer.find_answer(pMessage);
        print("Response: ",response);
        if response[0]!=None:
             if response[0][0]=='>':
                 for entry in self.command(response[0][1:], pMessage):
                     say(entry);
             else:
                 say(response[0]);
    def listen(self, audio):
        self.out(self.rec.recognize_google(audio, language='de-DE'));
    def initialize(self):
        with self.mic as source:
            self.rec.listen_in_background(source, self.listen);
    def run(self):
        while True:
            try:
                with self.mic as source:
                     audio = self.rec.listen(source, timeout=None);
                     self.out(self.rec.recognize_google(audio, language='de-DE'));
            except Exception as e:
                 print(e);

#speechrecog = SpeechRecognition();
#speechrecog.start();


setAlert("System started.");

try:
    while True:
        render();
        #time.sleep(1);
except KeyboardInterrupt:
    oled.onoff(False);
    oled.cls();
    GPIO.cleanup();
