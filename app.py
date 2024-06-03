import threading
import tkinter as tk

import ollama
import pygame
import pygame.camera
import pyttsx3
import speech_recognition as sr
from PIL import Image, ImageTk
from gtts import gTTS
import time

from utils.constants import DARK_GRAY_COLOR, PRIMARY_APP_COLOR, APP_CHAT_FONT, PERSONA_NAME_FONT, ANJALI_PERSONA
from utils.constants import ROBERT_PERSONA, SOFIA_PERSONA, ANJALI_VISION_PERSONA, SOFIA_TUTOR_PERSONA


from groq import Groq

from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=""
)



class ChatApp:
    def __init__(self, persona):

        self.avatar_loop = None

        # Set the persona of the ai companion
        self.persona = persona

        # Message List - To hold the conversation history
        self.messages = [
            {
                'role': 'system',
                'content': self.persona.system_prompts
            }
        ]

        # Setting up the overall frame
        self.root = tk.Tk()
        self.root.title("AI Buddy")
        self.root.geometry("450x800")

        # Configure root frame grid weights
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=3)
        self.root.grid_rowconfigure(2, weight=0)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=0)

        # Creating the avatar panel to display the avatar image
        self.avatar_panel = tk.Frame(self.root, bg='white')  # Dark background
        self.avatar_panel.grid(row=0, column=0, sticky="nsew")  # Grid placement
        self.avatar_panel.grid_rowconfigure(0, weight=1)  # Configure grid weights
        self.avatar_panel.grid_columnconfigure(0, weight=1)

        # Open and resize the image
        avatar_image_file = "./res/" + self.persona.path
        avatar_image = Image.open(avatar_image_file)
        self.avatar_frames_count = avatar_image.n_frames  # number of frames
        self.avatar_image_objects = []

        for x in range(self.avatar_frames_count):
            frame = ImageTk.PhotoImage(avatar_image.copy())
            self.avatar_image_objects.append(frame)
            avatar_image.seek(x)

        # Display image on the image panel
        self.avatar_image_lbl = tk.Label(self.avatar_panel, image="", bg="white")
        self.avatar_image_lbl.pack()
        self.avatar_image_lbl.configure(image=self.avatar_image_objects[0])

        # Create a label called emotion_status and display it as on overlay on the image panel
        self.avatar_name = tk.Label(self.avatar_panel, text=self.persona.name, bg="white", font=PERSONA_NAME_FONT)
        self.avatar_name.pack()

        # Create chat history display (flex container)
        self.chat_history = tk.Frame(self.root, bg=DARK_GRAY_COLOR)  # Dark background
        self.chat_history.grid(row=1, column=0, columnspan=2, sticky="nsew")  # Grid placement
        self.chat_history.grid_rowconfigure(0, weight=0)  # Configure grid weights
        self.chat_history.grid_columnconfigure(0, weight=1)

        # Create a bottom panel to add input field, send button and mic button
        self.bottom_panel = tk.Frame(self.root, bg="gray", height=100)  # Dark background
        self.bottom_panel.grid(row=2, column=0, columnspan=2, sticky="ew")  # Grid placement
        self.bottom_panel.grid_rowconfigure(0, weight=1)  # Configure grid weights
        self.bottom_panel.grid_columnconfigure(0, weight=1)

        # Create input field
        self.input_field = tk.Entry(self.bottom_panel, bg=DARK_GRAY_COLOR, fg="white")
        self.input_field.grid(row=0, column=0, sticky="news")  # Grid placement
        self.input_field.bind("<Return>", lambda action: self.send_message())

        # Load microphone icon image
        microphone_icon = Image.open("./res/microphone.png")  # Replace "microphone_icon.png" with your image file
        microphone_icon = microphone_icon.resize((32, 32))
        self.microphone_image = ImageTk.PhotoImage(microphone_icon)

        # Send/Microphone button
        self.microphone_button = tk.Button(self.bottom_panel, image=self.microphone_image, command=self.send_message,
                                           bg=PRIMARY_APP_COLOR)
        self.microphone_button.grid(row=0, column=1, sticky="e", padx=0, pady=0)  # Grid placement
        self.microphone_button.bind("<Button-1>", lambda action: self.listen())

    def send_message(self, text=''):
        message = self.input_field.get() if text == '' else text
        if message:
            # Take a webcam photo of the person
            # self.take_webcam_photo()

            # Append the message from the user to the messages list
            self.messages.append({'role': 'user',
                                  'content': message,})

            # Create a chat card for the sent message
            user_chat_card = tk.Frame(self.chat_history, bg=PRIMARY_APP_COLOR, padx=10, pady=5)
            user_chat_card.grid(sticky="e", pady=5, padx=10,
                                row=self.chat_history.grid_size()[1])  # Place at the bottom-right

            # Label to display the message inside the chat card
            user_label = tk.Label(user_chat_card, text=f"{message}", bg=PRIMARY_APP_COLOR, fg='white',
                                  wraplength=300, justify='left', font=APP_CHAT_FONT)
            # Align message text to the right within the chat card
            user_label.pack(anchor="e")

            # Clear input field after sending message
            self.input_field.delete(0, tk.END)

            self.chat_history.update_idletasks()  # Update the UI

            # Call the Ollama model to generate a response
            response = self.get_response(message)

            ai_chat_card = tk.Frame(self.chat_history, bg='gray', padx=10, pady=5)
            ai_chat_card.grid(sticky="w", pady=5, padx=10,
                              row=self.chat_history.grid_size()[1])  # Place at the bottom-right

            # Label to display the message inside the chat card
            ai_label = tk.Label(ai_chat_card, text=f"{response}", bg="gray", fg="white", wraplength=300,
                                justify='left', font=APP_CHAT_FONT)
            # Align message text to the left within the chat card
            ai_label.pack(anchor="w")

            # Create a new thread for speech synthesis
            # TODO: Currently only offline voices available for male voices so conditionally
            #  rendering online voice for Male vs Female. Change it in the future to render
            #  online voice for all the voices.
            speech_thread = threading.Thread(
                target=self.respond_online if self.persona.gender == 'female' else self.respond, args=(response,))
            speech_thread.start()

    def animate_avatar(self, current_frame=0):
        self.avatar_image_lbl.configure(image=self.avatar_image_objects[current_frame])
        current_frame = (current_frame + 1) % (self.avatar_frames_count - 8)
        self.avatar_loop = self.root.after(100, lambda: self.animate_avatar(current_frame))

    def stop_avatar(self):
        print('Stopping Animation')
        self.root.after_cancel(self.avatar_loop)
        self.avatar_image_lbl.configure(image=self.avatar_image_objects[0])
        # Set microphone button color to primary - TODO: Temporary Fix. Remove this from stop_avatar
        self.microphone_button.configure(bg=PRIMARY_APP_COLOR)

    def run(self):
        self.root.mainloop()

    def listen(self):
        # Turn the microphone button gray
        self.microphone_button.configure(bg="gray")
        self.microphone_button.update()
        print('Listening')
        r = sr.Recognizer()
        with sr.Microphone() as source:
            audio = r.listen(source)
            try:
                text = r.recognize_google(audio, language=self.persona.language)
                self.microphone_button.configure(bg=PRIMARY_APP_COLOR)
                self.send_message(text)
            except sr.UnknownValueError:
                print("Could not understand audio")
            except sr.RequestError as e:
                print("Could not request results; {0}".format(e))
            finally:
                self.microphone_button.configure(bg=PRIMARY_APP_COLOR)

    def get_response(self, query):
        chat_completion = client.chat.completions.create(
            messages= self.messages,
            model="llama3-8b-8192",
        )
        return chat_completion.choices[0].message.content
    def respond(self, response):
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        # print the list of voices available
        print(voices)
        engine.setProperty('voice', voices[0].id)
        engine.setProperty('rate', 150)
        engine.say(response)
        # Create a new thread and call animate_avatar function
        self.animate_avatar()
        engine.runAndWait()
        self.stop_avatar()
        engine.stop()

    def respond_online(self, response):

        # Set the language to indian english accent
        tts = gTTS(response, lang=self.persona.language)
        tts.save("./res/indian_tts.mp3")

        pygame.mixer.init()
        pygame.mixer.music.load("./res/indian_tts.mp3")
        pygame.mixer.music.play()
        # Create a new thread and call animate_avatar function
        self.animate_avatar()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.quit()
        # Remove the temporary file
        # os.remove("./res/indian_tts.mp3")
        self.stop_avatar()

    # Function to capture the webcam photo and store it as res/webcam_capture.jpg
    def take_webcam_photo(self):
        pygame.init()
        pygame.camera.init()
        time.sleep(1)
        cam_list = pygame.camera.list_cameras()
        if not cam_list:
            print("No cameras found.")
            exit()
        cam = pygame.camera.Camera(cam_list[0], (640, 480))
        cam.start()
        # Allow the camera to warm up
        time.sleep(1)
        # Capture an image
        image = cam.get_image()
        filename = './res/webcam_capture.jpg'
        pygame.image.save(image, filename)


if __name__ == "__main__":
    chat_app = ChatApp(SOFIA_TUTOR_PERSONA)
    chat_app.run()
