import customtkinter as ctk
import os
import threading
import time
import pygame
import cv2
import mediapipe as mp
from PIL import Image
import math
from focus_detector import FocusDetector
from brain import AdaptiveTimer

WORK_MIN = 25
SHORT_BREAK_MIN = 5
LONG_BREAK_MIN = 20
SESSIONS_BEFORE_LONG_BREAK = 4

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_PATH = os.path.join(BASE_DIR, "focus_memory.txt")

SOUND_SESSION_END = "assets/session_end.mp3"
SOUND_FOCUS_ALERT = "assets/focus_alert.mp3"

COLOR_TEXT = "#FFFFFF"
COLOR_WARN = "#FFCC00"


class PomodoroTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("Focus Guard")
        self.root.geometry("400x760")
        self.root.resizable(False, False)

        self.sessions = 0
        self.is_running = False
        self.is_paused = False
        self.current_session_type = "Work"
        self.timer_thread = None
        self.current_session_distractions = 0
        self.last_session_distractions = 0
        self.last_penalty_time = 0.0
        self.ai_brain = AdaptiveTimer(
            current_optimal_mins=WORK_MIN, memory_path=MEMORY_PATH
        )
        self.work_duration = int(self.ai_brain.optimal_mins) * 60
        self.current_time = self.work_duration
        self.break_duration = (
            int(math.sqrt(WORK_MIN)) * 60
        )  # Default break = sqrt(work)
        self.total_focus_time_goal = (
            WORK_MIN * 4 * 60
        )  # Default: 4 sessions worth (100 mins)
        self.total_sessions_needed = 4  # Default sessions to reach goal

        pygame.mixer.init()
        self.cap = None
        self.camera_active = False
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.drawing_spec = self.mp_drawing.DrawingSpec(
            thickness=1, circle_radius=1, color=(0, 255, 0)
        )

        self.unfocused_counter = 0
        self.VISUAL_WARNING_THRESHOLD_FRAMES = 15
        self.SOUND_ALERT_THRESHOLD_FRAMES = 45

        self.session_label = ctk.CTkLabel(root, text="", font=("Helvetica", 24, "bold"))
        self.session_label.pack(pady=10)

        self.timer_label = ctk.CTkLabel(root, text="", font=("Helvetica", 80, "bold"))
        self.timer_label.pack(pady=10)

        stats_frame = ctk.CTkFrame(root)
        stats_frame.pack(pady=5, fill="x", padx=20)

        self.next_focus_label = ctk.CTkLabel(
            stats_frame, text="", font=("Helvetica", 14)
        )
        self.next_focus_label.pack(pady=(8, 2))

        self.current_distractions_label = ctk.CTkLabel(
            stats_frame, text="", font=("Helvetica", 14)
        )
        self.current_distractions_label.pack(pady=2)

        self.last_distractions_label = ctk.CTkLabel(
            stats_frame, text="", font=("Helvetica", 14)
        )
        self.last_distractions_label.pack(pady=(2, 8))

        self.unfocused_reason_label = ctk.CTkLabel(
            root, text="", font=("Helvetica", 16), text_color=COLOR_WARN
        )
        self.unfocused_reason_label.pack(pady=5)

        # Focus Duration Setting
        duration_frame = ctk.CTkFrame(root)
        duration_frame.pack(pady=8, fill="x", padx=20)

        duration_label = ctk.CTkLabel(
            duration_frame,
            text="Focus Duration (mins):",
            font=("Helvetica", 12, "bold"),
        )
        duration_label.pack(side="left", padx=(0, 10))

        duration_options = [str(i) for i in range(5, 121, 5)]
        self.duration_combobox = ctk.CTkComboBox(
            duration_frame,
            values=duration_options,
            state="readonly",
            width=80,
            command=self.update_work_duration,
        )
        self.duration_combobox.set(str(WORK_MIN))
        self.duration_combobox.pack(side="left")

        # Total Focus Time Goal Setting
        total_frame = ctk.CTkFrame(root)
        total_frame.pack(pady=8, fill="x", padx=20)

        total_label = ctk.CTkLabel(
            total_frame,
            text="Total Focus Goal (mins):",
            font=("Helvetica", 12, "bold"),
        )
        total_label.pack(side="left", padx=(0, 10))

        total_options = [str(i) for i in range(30, 601, 30)]
        self.total_time_combobox = ctk.CTkComboBox(
            total_frame,
            values=total_options,
            state="readonly",
            width=80,
            command=self.update_total_focus_time,
        )
        self.total_time_combobox.set(str(int(self.total_focus_time_goal / 60)))
        self.total_time_combobox.pack(side="left")

        sessions_label = ctk.CTkLabel(
            total_frame,
            text=f"({self.total_sessions_needed} sessions)",
            font=("Helvetica", 11),
            text_color="#FFD700",
        )
        sessions_label.pack(side="left", padx=(10, 0))
        self.sessions_indicator = sessions_label

        # Break Duration Display
        break_duration_frame = ctk.CTkFrame(root)
        break_duration_frame.pack(pady=5, fill="x", padx=20)

        break_label = ctk.CTkLabel(
            break_duration_frame,
            text="Break Duration (auto-calculated):",
            font=("Helvetica", 12, "bold"),
        )
        break_label.pack(side="left", padx=(0, 10))

        self.break_duration_display = ctk.CTkLabel(
            break_duration_frame,
            text=f"{int(self.break_duration / 60)} mins",
            font=("Helvetica", 12),
            text_color="#00FF00",
        )
        self.break_duration_display.pack(side="left")

        # Quick Goals / To-Do Section
        goals_frame = ctk.CTkFrame(root)
        goals_frame.pack(pady=8, fill="x", padx=20)

        goals_label = ctk.CTkLabel(
            goals_frame, text="Quick Goals", font=("Helvetica", 12, "bold")
        )
        goals_label.pack(anchor="w", pady=(0, 5))

        goals_input_frame = ctk.CTkFrame(goals_frame, fg_color="transparent")
        goals_input_frame.pack(fill="x", pady=(0, 5))

        self.goal_entry = ctk.CTkEntry(
            goals_input_frame, placeholder_text="Add a quick goal...", height=28
        )
        self.goal_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.goal_entry.bind("<Return>", lambda e: self.add_goal())

        self.add_goal_button = ctk.CTkButton(
            goals_input_frame, text="+", command=self.add_goal, width=30
        )
        self.add_goal_button.pack(side="left")

        self.goals_list_frame = ctk.CTkFrame(goals_frame)
        self.goals_list_frame.pack(fill="both", expand=True)

        self.goals = []
        self.session_goals = []  # Track goals for current session

        control_frame = ctk.CTkFrame(root, fg_color="transparent")
        control_frame.pack(pady=10)

        self.start_button = ctk.CTkButton(
            control_frame, text="Start", command=self.start_timer, width=100
        )
        self.start_button.pack(side="left", padx=5)

        self.pause_button = ctk.CTkButton(
            control_frame,
            text="Pause",
            command=self.pause_timer,
            width=100,
            state="disabled",
        )
        self.pause_button.pack(side="left", padx=5)

        self.reset_button = ctk.CTkButton(
            control_frame, text="Reset", command=self.reset_timer, width=100
        )
        self.reset_button.pack(side="left", padx=5)

        self.webcam_label = ctk.CTkLabel(root, text="")
        self.webcam_label.pack(pady=10)

        self.update_display()
        self.update_webcam()

    def play_sound(self, sound_file):
        try:
            pygame.mixer.music.load(sound_file)
            pygame.mixer.music.play()
        except pygame.error as e:
            print(f"Cannot play sound: {e}. Check the file path and assets folder.")

    def update_display(self):
        mins, secs = divmod(self.current_time, 60)
        self.timer_label.configure(text=f"{mins:02d}:{secs:02d}")
        self.session_label.configure(
            text=f"{self.current_session_type} Session ({self.sessions}/{self.total_sessions_needed})"
        )
        self.next_focus_label.configure(
            text=f"Next Focus: {int(self.work_duration / 60)} min"
        )
        self.current_distractions_label.configure(
            text=f"Session Distractions: {self.current_session_distractions}"
        )
        self.last_distractions_label.configure(
            text=f"Last Session Distractions: {self.last_session_distractions}"
        )
        # Update break duration display
        self.break_duration_display.configure(
            text=f"{int(self.break_duration / 60)} mins"
        )

    def add_goal(self):
        goal_text = self.goal_entry.get().strip()
        if goal_text:
            self.goals.append(goal_text)
            self.goal_entry.delete(0, "end")
            self.update_goals_display()

    def update_work_duration(self, value=None):
        try:
            new_duration = int(self.duration_combobox.get())
            self.work_duration = new_duration * 60
            # Recalculate break duration as sqrt(work_duration)
            self.break_duration = int(math.sqrt(new_duration)) * 60
            self.recalculate_sessions_needed()
            if not self.is_running:
                self.current_time = self.work_duration
                self.update_display()
        except ValueError:
            pass

    def update_total_focus_time(self, value=None):
        try:
            new_total = int(self.total_time_combobox.get())
            self.total_focus_time_goal = new_total * 60
            self.recalculate_sessions_needed()
            if not self.is_running:
                self.update_display()
        except ValueError:
            pass

    def recalculate_sessions_needed(self):
        work_mins = int(self.work_duration / 60)
        total_mins = int(self.total_focus_time_goal / 60)
        self.total_sessions_needed = max(1, total_mins // work_mins)
        self.sessions_indicator.configure(
            text=f"({self.total_sessions_needed} sessions)"
        )

    def remove_goal(self, index):
        if 0 <= index < len(self.goals):
            self.goals.pop(index)
            self.update_goals_display()

    def show_session_completion_dialog(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Session Complete!")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        dialog.grab_set()

        # Center the dialog on the root window
        dialog.transient(self.root)
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = (
            self.root.winfo_y()
            + (self.root.winfo_height() - dialog.winfo_height()) // 2
        )
        dialog.geometry(f"+{x}+{y}")

        # Congratulations heading
        congrats_label = ctk.CTkLabel(
            dialog,
            text="🎉 Congratulations! 🎉",
            font=("Helvetica", 20, "bold"),
            text_color="#00FF00",
        )
        congrats_label.pack(pady=15)

        message_label = ctk.CTkLabel(
            dialog,
            text="You've completed a focused work session!",
            font=("Helvetica", 14),
        )
        message_label.pack(pady=10)

        # Goals completed section
        if self.session_goals:
            goals_heading = ctk.CTkLabel(
                dialog, text="Goals Completed:", font=("Helvetica", 12, "bold")
            )
            goals_heading.pack(pady=(10, 5))

            goals_text_frame = ctk.CTkFrame(dialog)
            goals_text_frame.pack(pady=5, padx=20, fill="both", expand=True)

            goals_display = ctk.CTkTextbox(goals_text_frame, height=120, width=350)
            goals_display.pack(fill="both", expand=True)
            goals_display.configure(state="normal")

            for goal in self.session_goals:
                goals_display.insert("end", f"✓ {goal}\n")

            goals_display.configure(state="disabled")
        else:
            no_goals_label = ctk.CTkLabel(
                dialog,
                text="No goals set for this session.",
                font=("Helvetica", 12),
                text_color="#CCCCCC",
            )
            no_goals_label.pack(pady=20)

        # Close button
        close_button = ctk.CTkButton(
            dialog, text="Continue", command=dialog.destroy, font=("Helvetica", 12)
        )
        close_button.pack(pady=15)

    def show_break_completion_dialog(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Break Complete!")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        dialog.grab_set()

        # Center the dialog on the root window
        dialog.transient(self.root)
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = (
            self.root.winfo_y()
            + (self.root.winfo_height() - dialog.winfo_height()) // 2
        )
        dialog.geometry(f"+{x}+{y}")

        # Reward heading
        reward_label = ctk.CTkLabel(
            dialog,
            text="✨ Great Job! ✨",
            font=("Helvetica", 20, "bold"),
            text_color="#FFD700",
        )
        reward_label.pack(pady=15)

        message_label = ctk.CTkLabel(
            dialog,
            text="You've earned your well-deserved break!",
            font=("Helvetica", 14),
        )
        message_label.pack(pady=10)

        rest_message = ctk.CTkLabel(
            dialog,
            text="Get refreshed and ready for the next session!",
            font=("Helvetica", 12),
            text_color="#00FF00",
        )
        rest_message.pack(pady=10)

        # Close button
        close_button = ctk.CTkButton(
            dialog, text="Continue", command=dialog.destroy, font=("Helvetica", 12)
        )
        close_button.pack(pady=15)

    def update_goals_display(self):
        for widget in self.goals_list_frame.winfo_children():
            widget.destroy()

        for i, goal in enumerate(self.goals):
            goal_item_frame = ctk.CTkFrame(
                self.goals_list_frame, fg_color="transparent"
            )
            goal_item_frame.pack(fill="x", pady=2)

            goal_label = ctk.CTkLabel(
                goal_item_frame,
                text=f"• {goal}",
                font=("Helvetica", 11),
                justify="left",
            )
            goal_label.pack(side="left", fill="x", expand=True, anchor="w")

            delete_btn = ctk.CTkButton(
                goal_item_frame,
                text="✓",
                command=lambda idx=i: self.remove_goal(idx),
                width=25,
                height=20,
                font=("Helvetica", 10),
            )
            delete_btn.pack(side="right", padx=(5, 0))

    def countdown(self):
        while self.is_running and self.current_time > 0:
            if not self.is_paused:
                self.current_time -= 1
                self.root.after(0, self.update_display)
                time.sleep(1)

        if self.is_running and self.current_time == 0:
            self.play_sound(SOUND_SESSION_END)
            self.root.after(0, self.on_timer_complete)

    def start_timer(self):
        if not self.is_running:
            self.is_running = True
            self.start_button.configure(state="disabled")
            self.pause_button.configure(state="normal")
            self.duration_combobox.configure(state="disabled")
            if self.current_session_type == "Work":
                self.session_goals = self.goals.copy()  # Save goals at start of session
                self.start_camera()
            self.timer_thread = threading.Thread(target=self.countdown, daemon=True)
            self.timer_thread.start()

    def pause_timer(self):
        self.is_paused = not self.is_paused
        self.pause_button.configure(text="Resume" if self.is_paused else "Pause")

    def reset_timer(self):
        self.is_running = False
        self.is_paused = False
        self.sessions = 0
        self.current_session_type = "Work"
        self.work_duration = int(self.duration_combobox.get()) * 60
        self.break_duration = int(math.sqrt(int(self.duration_combobox.get()))) * 60
        self.total_focus_time_goal = int(self.total_time_combobox.get()) * 60
        self.recalculate_sessions_needed()
        self.current_time = self.work_duration
        self.current_session_distractions = 0
        self.last_session_distractions = 0
        self.last_penalty_time = 0.0
        self.goals = []
        self.session_goals = []
        self.stop_camera()
        self.update_display()
        self.update_goals_display()
        self.start_button.configure(state="normal")
        self.pause_button.configure(state="disabled", text="Pause")
        self.duration_combobox.configure(state="readonly")
        self.unfocused_reason_label.configure(text="")

    def on_timer_complete(self):
        if self.current_session_type == "Work":
            self.stop_camera()
            self.last_session_distractions = self.current_session_distractions
            next_focus_time = self.ai_brain.calculate_next_session(
                self.current_session_distractions
            )
            print(
                f"Session ended with {self.current_session_distractions} distractions."
            )
            print(f"AI adjusted next focus session to: {next_focus_time} minutes.")

            # Constrain algorithm changes to max ±25% per session
            current_work_mins = int(self.work_duration / 60)
            max_increase = current_work_mins * 1.25
            min_decrease = current_work_mins * 0.75
            next_focus_time = max(min(next_focus_time, max_increase), min_decrease)

            self.work_duration = next_focus_time * 60
            # Calculate break time as sqrt(work_duration)
            self.break_duration = int(math.sqrt(next_focus_time)) * 60
            print(f"AI constrained next focus session to: {next_focus_time} minutes.")
            print(f"Break time calculated as: {int(self.break_duration / 60)} minutes.")

            # Recalculate total sessions needed based on new work duration
            self.recalculate_sessions_needed()

            self.current_session_distractions = 0
            self.last_penalty_time = 0.0
            self.update_display()

            # Show completion dialog with goals
            self.show_session_completion_dialog()
        elif self.current_session_type in ["Short Break", "Long Break"]:
            # Show reward screen after break sessions too
            self.show_break_completion_dialog()

        self.next_session()

    def next_session(self):
        if self.current_session_type == "Work":
            self.sessions += 1
            if self.sessions % SESSIONS_BEFORE_LONG_BREAK == 0:
                self.current_session_type = "Long Break"
                self.current_time = LONG_BREAK_MIN * 60
            else:
                self.current_session_type = "Short Break"
                self.current_time = self.break_duration  # Use calculated break duration
        else:
            self.current_session_type = "Work"
            self.current_time = self.work_duration
            self.current_session_distractions = 0
            self.last_penalty_time = 0.0
            if self.is_running:
                self.start_camera()

        self.is_paused = False
        self.update_display()

        self.timer_thread = threading.Thread(target=self.countdown, daemon=True)
        self.timer_thread.start()

    def update_webcam(self):
        if not self.camera_active:
            self.webcam_label.configure(image=None)
            self.root.after(200, self.update_webcam)
            return

        if self.cap is None or not self.cap.isOpened():
            self.start_camera()

        ret, frame = self.cap.read()
        if not ret:
            self.root.after(200, self.update_webcam)
            return

        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)

        is_focus_module_active = (
            self.current_session_type == "Work"
            and self.is_running
            and not self.is_paused
        )

        if results.multi_face_landmarks and is_focus_module_active:
            for face_landmarks in results.multi_face_landmarks:
                self.mp_drawing.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=self.mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.drawing_spec,
                )

            detector = FocusDetector(results.multi_face_landmarks[0].landmark)
            unfocused_reason = detector.is_unfocused()

            if unfocused_reason:
                self.unfocused_counter += 1

                if self.unfocused_counter > self.VISUAL_WARNING_THRESHOLD_FRAMES:
                    self.unfocused_reason_label.configure(
                        text=f"Warning: {unfocused_reason}"
                    )

                if self.unfocused_counter > self.SOUND_ALERT_THRESHOLD_FRAMES:
                    self.play_sound(SOUND_FOCUS_ALERT)
                    now = time.time()
                    if now - self.last_penalty_time > 10:
                        self.current_session_distractions += 1
                        self.last_penalty_time = now
                        self.current_distractions_label.configure(
                            text=f"Session Distractions: {self.current_session_distractions}"
                        )
                    self.unfocused_counter = 0
            else:
                self.unfocused_counter = 0
                self.unfocused_reason_label.configure(text="")
        else:
            self.unfocused_counter = 0
            self.unfocused_reason_label.configure(text="")

        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(360, 270))
        self.webcam_label.configure(image=ctk_img)

        self.root.after(10, self.update_webcam)

    def start_camera(self):
        if self.camera_active:
            return

        self.cap = cv2.VideoCapture(0)
        self.camera_active = True

    def stop_camera(self):
        if not self.camera_active:
            return

        self.camera_active = False
        if self.cap is not None:
            self.cap.release()
        self.cap = None

    def on_closing(self):
        print("Closing app...")
        self.is_running = False
        self.stop_camera()
        self.root.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    app = PomodoroTimer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
