import RPi.GPIO as GPIO
import picamera
from picamera.array import PiRGBArray
import cv2
from lib_tft144 import TFT144
import spidev
import sys
import os
import time
from threading import Thread
import subprocess
from datetime import datetime
import Adafruit_DHT
import speech_recognition
import random
import wikipedia
import pyowm


GPIO.setwarnings(False);
GPIO.setmode(GPIO.BCM);

##Screen
screen = TFT144(GPIO, spidev.SpiDev(), 0, 27, 22, orientation=TFT144.ORIENTATION180);
screen.draw_array(cv2.imread('res/jarvis.png',cv2.IMREAD_COLOR), (128,85), y0=21);
render_mode = 0;
applied_mode = 1;

wikipedia.set_lang('de');

last_voice = 0;
speaking = 0;

def alert(pMessage):
    print("Alert: " + pMessage);
    screen.put_string(pMessage, 10, 110, screen.WHITE, screen.BLACK);

alert("Starting...");

def voiceCommand(pCommand, pSaid):
    split = pCommand.split(" ");
    if split[0] == 'time':
        yield "Es ist " + str(data.time.hour) + " Uhr und " + str(data.time.minute) + " Minuten.";
    elif split[0] == 'restart':
        yield "Neustart angefordert.";
        exit(command='sudo reboot');
    elif split[0] == 'shutdown':
        yield "Herunterfahren angefordert.";
        exit(command='sudo shutdown -h now');
    elif split[0] == 'wiki':
        searchfor = pSaid.lower().split(split[1].replace('_',' '))[1];
        yield "Such nach " + searchfor + ".";
        result = wikipedia.summary( searchfor );
        split = result.split('.');
        if len(split)>3:
            result = '';
            for i in range(3):
                result+=split[i] + '. ';
        yield result;
    elif split[0] == 'weather':
        if split[1] == 'today':
            we = weather_system.getCurrentWeather();
            yield "Temperatur: " + str(we['temperature']) + "°C";
            yield "Luftfeuchtigkeit: " + str(we['humidity']) + "%";
            yield "Windgeschwindigkeit: " + str(we['wind']) + " km/h";
            yield "Bewölkung: " + str(we['clouds']) + "%";
        elif split[1] == 'tomorrow':
            we = weather_system.getCurrentWeather();
            yield "Temperatur am Tag: " + str(we['temperature']) + "°C";
            yield "Temperatur in der Nacht: " + str(we['temperature_night']) + "°C";
            yield "Luftfeuchtigkeit: " + str(we['humidity']) + "%";
            yield "Windgeschwindigkeit: " + str(we['wind']) + " km/h";
            yield "Bewölkung: " + str(we['clouds']) + "%";  
        

def voiceTrigger(channel):
    global last_voice;
    if time.time()-last_voice<1 or speaking==1:
        return;
    last_voice = time.time();
    if render_mode == 3:
        global recording,recording_start,recording_file,applied_mode;
        if recording:
            try:
                camera.stop_recording();
            except Exception:
                pass;
            recording = False;
            applied_mode = 0;
        else:
            recording_file = str(len(list(os.listdir('capture/video')))) + '.h264';
            camera.start_recording('capture/video/' + recording_file);
            recording_start = int(time.time());
            recording=True;
            applied_mode = 0;
        buzz();
    elif render_mode == 4:
        global photo_file,applied_mode;
        photo_file = str(len(list(os.listdir('capture/photo')))) + '.jpg';
        buzz();
        camera.capture('capture/photo/' + photo_file);
        applied_mode = 0;
    elif render_mode == 5:
        buzz();
        global speaking,speak_answer,applied_mode;
        speaking=1;
        applied_mode = 0;
        result = voice_parser.timedListen();
        buzz();
        alert("Processing...");
        print("Heard: ", result);
        if result != None:
            answer = answer_bot.find_answer(result);
            print("Answer: ", answer);
            if answer != None:
                if answer[0] == '>':
                    for entry in voiceCommand(answer[1:], result):
                        say(entry);
                        speak_answer = entry;
                else:
                    speak_answer = answer;
                    say(speak_answer);
                speaking=2;
                applied_mode = 0;
            else:
                speak_answer='No answer.';
                say('Keine Antwort. Ich habe verstanden: ' + result);
        else:
            speak_answer='Failed.';
            say('Kein Ergebnis.');
        speaking=2;
        applied_mode = 0;
        

mode_names = {0:'Standard', 1:'Zoom', 2:'Temperatur',3:'Video',4:'Foto',5:'Sprache'};

alert("Setting up GPIO...");

def buzz(length=0.02):
    GPIO.output(12, True);
    time.sleep(length);
    GPIO.output(12, False);

def viewTrigger(channel):
    global last_view_change;
    if time.time()-last_view_change>1:
        last_view_change = time.time();
        global render_mode;
        render_mode += 1;
        if render_mode > 5:
            render_mode = 0;
        say(mode_names[render_mode]);

GPIO.setup(4, GPIO.IN, pull_up_down=GPIO.PUD_UP);
GPIO.add_event_detect(4, GPIO.FALLING, callback=voiceTrigger);
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP);
GPIO.add_event_detect(17, GPIO.FALLING, callback=viewTrigger);
GPIO.setup(12, GPIO.OUT);

last_view_change = 0;

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
                        self.data.append([entry.split(','), answers]);
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
                    return random.choice(entry[1]);
                else:
                    return random.choice(entry[1]);
        return None;

class VoiceParser:
    def optimize_threshold(self):
        with speech_recognition.Microphone(device_index=2) as source:
            self.rec.adjust_for_ambient_noise(source, duration=1);

    def __init__(self):
        self.rec = speech_recognition.Recognizer();
        self.mic = speech_recognition.Microphone(device_index=2);
        self.rec.pause_threshold = 0.5;
        self.rec.operation_timeout = 2;
    def timedListen(self, time=4):
        os.system('arecord -D plughw:1 -r 16000 tmp.wav -q -d ' + str(time));
        with speech_recognition.AudioFile('tmp.wav') as file:
            audio = self.rec.record(file);
            try:
                return self.rec.recognize_google(audio, language='de-DE');
            except Exception:
                return None;
    def listen(self):
        with self.mic as source:
            print("...STARTING...");
            audio = self.rec.listen(self.mic);
            print("...FINISHED...");
            try:
                return self.rec.recognize_google(audio, language='de-DE');
            except Exception:
                return None;

alert("Loading voice data...");
answer_bot = AnswerBot('de.txt');
voice_parser = VoiceParser();

class WeatherSystem:
    def __init__(self):
        self.owm = pyowm.OWM('633e59a3ba58f519fc6e1cf835b7ff6b');

    def simplify(self, w, is_forecast=False):
        if is_forecast:
            return {'temperature':w.get_temperature('celsius')['day'], 
                    'temperature_night':w.get_temperature('celsius')['night'],
                    'humidity':w.get_humidity(), 
                    'wind':int(w.get_wind()['speed']*3.6),
                    'visibility':w.get_visibility_distance(),
                    'clouds':w.get_clouds() 
                   };  
        else:
            return {'temperature':w.get_temperature('celsius')['temp'], 
                    'humidity':w.get_humidity(), 
                    'wind':int(w.get_wind()['speed']*3.6),
                    'visibility':w.get_visibility_distance(),
                    'clouds':w.get_clouds() 
                   };  
      
    def getCurrentWeather(self):
        w = self.owm.weather_at_place("Wuppertal,de").get_weather();
        return self.simplify(w);

    def getWeatherTomorrow(self):
        f = self.owm.daily_forecast("Wuppertal,de");
        w = f.get_weather_at(pyowm.timeutils.tomorrow());
        return self.simplify(w, is_forecast=True);

alert("Connecting to OWM...");
weather_system = WeatherSystem();

def say(pString, lang='de-DE'):
    os.system('pico2wave --lang=' + lang + ' --wave=/tmp/voiceout.wav "' + pString + '"');
    os.system('aplay /tmp/voiceout.wav');

alert("Loading camera...");
##Camera
camera = picamera.PiCamera();
camera.resolution=(int(128*8),int(96*8));
camera.framerate=25;
camera.exposure_mode='night';
recording = False;
default_size = (int(camera.resolution[0]*0.125), int(camera.resolution[1]*0.125));
scale_size = (int(camera.resolution[0]*0.0625), int(camera.resolution[1]*0.0625));
zoom = (int(camera.resolution[1]*0.25), int(camera.resolution[1]*0.75), int(camera.resolution[0]*0.25), int(camera.resolution[0]*0.75));
raw = PiRGBArray(camera, size=camera.resolution);

class CameraStreamer(Thread):
    def __init__(self):
        Thread.__init__(self, daemon=True);
    def run(self):
        self.current_image = None;
        for image in camera.capture_continuous(raw, format='bgr', use_video_port=True):
            self.current_image = image.array;
            raw.truncate(0);
    def runOld(self):
        while True:
            camera.capture('tmp.bmp', format='bmp');
            screen.draw_bmp('tmp.bmp', y0=36);
streamer = CameraStreamer();
streamer.start();

alert("Starting data streamer...");
class DataStreamer(Thread):
    def __init__(self):
        Thread.__init__(self, daemon=True);
        self.processor_temp = 0;
        self.time = datetime.now();
        self.tempdata = (0,0);
    def run(self):
        while True:
            tmp = subprocess.check_output(['vcgencmd', 'measure_temp']).decode();
            tmp = tmp[5:len(tmp)-3];
            self.processor_temp = tmp;
            self.time = datetime.now();
            tmp = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, 26);
            if(tmp[0]!=None):
                self.tempdata = tmp;
            time.sleep(1);

data = DataStreamer();
data.start();

render_step = 11;
def render():
    global applied_mode,render_step,drawn_tempdata;
    if applied_mode != render_mode:
        screen.clear_display(screen.BLACK);
        screen.put_string(mode_names[render_mode], 10, 10, screen.WHITE, screen.BLACK);
        applied_mode = render_mode;        
        if render_mode == 2:
            screen.draw_line(10, 100, 10, 128, screen.WHITE);
            screen.draw_line(10, 128, 128, 128, screen.WHITE);
            for y in range(0,3):
                screen.draw_line(0,128-y*10,10,128-y*10, screen.WHITE);
            render_step = 11;
        elif render_mode == 3:
            if not recording:
                screen.put_string('Bereit. Total: ' + str(len(list(os.listdir('capture/video')))), 10, 40, screen.WHITE, screen.BLACK); 
            else:
                screen.put_string(recording_file, 10, 55, screen.WHITE, screen.BLACK);
        elif render_mode == 4:
            screen.put_string('Fotozahl: ' + str(len(list(os.listdir('capture/photo')))), 10, 40, screen.WHITE, screen.BLACK);
        elif render_mode == 5:
            if speaking==0:
                screen.put_string('Ready to listen.', 10, 30, screen.WHITE, screen.BLACK);
            elif speaking==1:
                screen.put_string('Listening...', 10, 30, screen.WHITE, screen.BLACK);
            elif speaking==2:
                screen.put_string('Ready to listen.', 10, 30, screen.WHITE, screen.BLACK);
                screen.put_string(speak_answer, 10, 45, screen.GREY, screen.BLACK);
    if render_mode == 0:
        if streamer.current_image != None:
            screen.draw_array(cv2.resize(streamer.current_image, default_size, interpolation = cv2.INTER_CUBIC), default_size, y0=36);
    elif render_mode == 1:
        if streamer.current_image != None:
            screen.draw_array(streamer.current_image[zoom[0]:zoom[1], zoom[2]:zoom[3]], default_size, y0=36);
    elif render_mode == 2:
        if streamer.current_image != None:
            screen.draw_array(cv2.resize(streamer.current_image, scale_size, interpolation = cv2.INTER_CUBIC), scale_size, y0=36);
        screen.put_string(str(data.time.hour) + ':' + str(data.time.minute) + ':' + str(data.time.second), 70, 40, screen.WHITE, screen.BLACK);
        if data.tempdata[0]!=0:
            screen.put_string(str(data.tempdata[0])[:7] + '%', 20, 88, screen.BLUE, screen.BLACK);
            screen.put_string(str(data.tempdata[1])[:7] + ' Grad', 20, 98, screen.RED, screen.BLACK);
            screen.draw_dot(int(render_step), int(128-(data.tempdata[0]/60)*20), screen.BLUE);
            screen.draw_dot(int(render_step), int(128-(data.tempdata[1]/60)*20), screen.RED);
            render_step+=0.1;
            if render_step>120:
                applied_mode = 0;  
    elif render_mode == 3:
        screen.draw_array(cv2.resize(streamer.current_image, scale_size, interpolation = cv2.INTER_CUBIC), scale_size, y0=80);
        if recording:
            screen.put_string('Videoaufnahme ' + str(int(time.time()-recording_start)) + 's', 10, 40, screen.RED, screen.BLACK);
    elif render_mode == 4:
        screen.draw_array(cv2.resize(streamer.current_image, scale_size, interpolation = cv2.INTER_CUBIC), scale_size, y0=80);
    elif render_mode == 5:
        screen.draw_array(cv2.resize(streamer.current_image, scale_size, interpolation = cv2.INTER_CUBIC), scale_size, y0=80);

    screen.put_string(str(data.processor_temp), 100, 10, screen.YELLOW, screen.BLACK);
def exit(command=None):
    screen.clear_display(screen.BLACK);
    screen.put_string("System not running.", 10, 110, screen.WHITE, screen.BLACK);
    screen.draw_array(cv2.imread('res/jarvis.png',cv2.IMREAD_COLOR), (128,85), y0=21);
    GPIO.cleanup();
    if command!=None:
        os.system(command);
    sys.exit(0);

buzz();
say("Wilkommen");
try:
    while True:
        render();
except KeyboardInterrupt:
    exit();  

