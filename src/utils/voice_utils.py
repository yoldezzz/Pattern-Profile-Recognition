import speech_recognition as sr
import pyttsx3
import os

def voice_to_text(audio_file_path: str) -> str:
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file_path) as source:
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.record(source)
            text = recognizer.recognize_sphinx(audio)
            return text
    except Exception as e:
        return f"Error processing audio: {str(e)}"

def text_to_voice(text: str, output_path: str = "output.wav"):
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 0.9)
    engine.save_to_file(text, output_path)
    engine.runAndWait()
    return output_path