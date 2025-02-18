"""
Copyright (c) 2025 Frk_izzyTTV
All rights reserved.

This program is protected by copyright law and international treaties.
Unauthorized reproduction or distribution of this program, or any portion of it,
may result in severe civil and criminal penalties.

Created by: Frk_izzyTTV
"""

import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, colorchooser, ttk
import json
import time
import os
from pathlib import Path
from datetime import datetime
import msvcrt  # Windows-specific file locking
import jsonschema  # for JSON schema validation
import threading
from functools import partial

# Set up application paths
APP_DATA = Path(os.path.expandvars(r"%LOCALAPPDATA%\Checklist"))
TASKS_FILE = APP_DATA / "tasks.json"
THEME_FILE = APP_DATA / "theme_preferences.json"
CATEGORY_FILE = APP_DATA / "categories.json"
TIME_FORMAT_FILE = APP_DATA / "time_format_preferences.json"
LOCK_FILE = APP_DATA / "checklist.lock"

# JSON Schema for task validation
TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "string"},
        "tasks": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["text", "done", "created_time", "priority", "bold", "id", "categories"],
                        "properties": {
                            "text": {"type": "string"},
                            "done": {"type": "boolean"},
                            "created_time": {"type": "string"},
                            "completed_time": {"type": ["string", "null"]},
                            "priority": {"type": "string", "enum": ["high", "medium", "low", "none"]},
                            "bold": {"type": "boolean"},
                            "id": {"type": "integer"},
                            "categories": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            }
        }
    }
}

class FileLock:
    def __init__(self, file_path):
        self.file_path = file_path
        self.lock_file = None
        self.locked = False
        
    def __enter__(self):
        try:
            # Open the lock file in append mode
            self.lock_file = open(self.file_path, 'a')
            
            # Try to acquire lock
            while True:
                try:
                    # Try to lock the entire file
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    self.locked = True
                    break
                except OSError:
                    time.sleep(0.1)  # Wait briefly before retrying
                    continue
                    
            return self
        except Exception as e:
            if self.lock_file:
                if self.locked:
                    try:
                        msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    except:
                        pass
                self.lock_file.close()
            raise Exception("Another instance is currently accessing the files. Please try again later.") from e
            
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            if self.locked:
                try:
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                except:
                    pass
            self.lock_file.close()

# Ensure directory exists
APP_DATA.mkdir(parents=True, exist_ok=True)

# Custom button style
class ModernButton(tk.Button):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=kwargs.get('bg', '#ffffff'),
            padx=15,
            pady=5,
            cursor="hand2"  # Hand cursor on hover
        )
        # Bind hover effects
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        
    def on_enter(self, e):
        self.configure(
            highlightbackground=self.cget('fg'),
            highlightthickness=2
        )
        
    def on_leave(self, e):
        self.configure(
            highlightbackground=self.cget('bg'),
            highlightthickness=1
        )

class ModernColorButton(tk.Button):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=5,
            bg="#3498db",
            fg="white",
            activebackground="#2980b9",
            activeforeground="white",
            font=("Arial", 9)
        )
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
    
    def on_enter(self, e):
        self.configure(bg="#2980b9")
    
    def on_leave(self, e):
        self.configure(bg="#3498db")

    def update_colors(self):
        self.configure(
            bg="#3498db",
            fg="white",
            activebackground="#2980b9",
            activeforeground="white"
        )

# Task management class
class TaskManager:
    PRIORITY_SYMBOLS = {
        "high": "",    # Red circle
        "medium": "",  # Yellow circle
        "low": "",     # Green circle
        "none": ""      # No symbol
    }
    
    TASKS_PER_PAGE = 20  # Number of tasks to show per page

    def __init__(self):
        self.tasks = {"All": []}
        self.current_category = "All"
        self.categories = ["All"]  # Track categories
        self._default_bold = False  # Add default bold state
        self.current_page = 0
        self.total_pages = 0
        self.load_categories()
        self.load_tasks()
        
    def get_current_page_tasks(self):
        """Get tasks for the current page only"""
        start_idx = self.current_page * self.TASKS_PER_PAGE
        end_idx = start_idx + self.TASKS_PER_PAGE
        return self.tasks[self.current_category][start_idx:end_idx]
        
    def get_total_pages(self):
        """Calculate total number of pages for current category"""
        total_tasks = len(self.tasks[self.current_category])
        return (total_tasks + self.TASKS_PER_PAGE - 1) // self.TASKS_PER_PAGE
        
    def next_page(self):
        """Move to next page if available"""
        if self.current_page < self.get_total_pages() - 1:
            self.current_page += 1
            return True
        return False
        
    def prev_page(self):
        """Move to previous page if available"""
        if self.current_page > 0:
            self.current_page -= 1
            return True
        return False
        
    def go_to_page(self, page):
        """Go to specific page if valid"""
        total_pages = self.get_total_pages()
        if 0 <= page < total_pages:
            self.current_page = page
            return True
        return False
        
    def toggle_default_bold(self):
        self._default_bold = not self._default_bold
        return self._default_bold

    def create_task(self, text):
        """Create a new task with default values"""
        return {
            "text": text,
            "done": False,
            "created_time": time.strftime("%Y-%m-%d %H:%M"),
            "completed_time": None,
            "priority": "none",
            "bold": self._default_bold,  # Use default bold state
            "id": int(time.time() * 1000),  # Use timestamp for unique ID
            "categories": ["All"]  # Track which categories this task belongs to
        }

    def add_category(self, name):
        if name and name not in self.categories:
            self.categories.append(name)
            self.save_categories()
            return True
        return False
    
    def edit_category(self, old_name, new_name):
        if old_name == "All" or new_name in self.categories:
            return False
        
        if old_name in self.categories:
            idx = self.categories.index(old_name)
            self.categories[idx] = new_name 
            self.save_categories()
            return True
        return False
    
    def remove_category(self, name):
        if name != "All" and name in self.categories:
            # Move tasks to "All" category if they're not already there
            for task in self.tasks[name]:
                if task not in self.tasks["All"]:
                    self.tasks["All"].append(task)
            
            self.categories.remove(name)
            del self.tasks[name]
            
            if self.current_category == name:
                self.current_category = "All"
            
            self.save_categories()
            return True
        return False
        
    def normalize_task(self, task):
        """Ensure task has all required fields with default values"""
        default_task = self.create_task("")
        
        # Validate task data type
        if not isinstance(task, dict):
            return default_task
            
        # Ensure all required fields exist and have correct types
        try:
            task_copy = task.copy()
            task_copy["text"] = str(task.get("text", ""))
            task_copy["done"] = bool(task.get("done", False))
            task_copy["created_time"] = str(task.get("created_time", time.strftime("%Y-%m-%d %H:%M")))
            task_copy["completed_time"] = str(task.get("completed_time", "")) if task.get("completed_time") else None
            task_copy["priority"] = str(task.get("priority", "none"))
            task_copy["bold"] = bool(task.get("bold", False))
            task_copy["id"] = int(task.get("id", int(time.time() * 1000)))
            task_copy["categories"] = list(task.get("categories", ["All"]))
            
            # Validate priority value
            if task_copy["priority"] not in ["high", "medium", "low", "none"]:
                task_copy["priority"] = "none"
                
            return task_copy
        except (ValueError, TypeError, AttributeError):
            return default_task
        
    def load_categories(self):
        if CATEGORY_FILE.is_file():
            with open(CATEGORY_FILE, 'r') as f:
                self.categories = json.load(f)
        else:
            self.categories = ['All']  # Default category

    def save_categories(self):
        with open(CATEGORY_FILE, 'w') as f:
            json.dump(self.categories, f)

    def load_tasks(self):
        try:
            if TASKS_FILE.exists():
                with open(TASKS_FILE, "r", encoding='utf-8') as file:
                    data = json.load(file)
                    if isinstance(data, dict) and "tasks" in data:
                        # Initialize empty categories
                        self.tasks = {category: [] for category in self.categories}
                        
                        # Load tasks from the All category
                        for task_data in data["tasks"].get("All", []):
                            task = self.normalize_task(task_data)
                            # Add task to each of its categories
                            for category in task["categories"]:
                                if category not in self.categories:
                                    self.categories.append(category)
                                if category in self.tasks:
                                    self.tasks[category].append(task)
                    else:
                        self.tasks = {"All": []}
            else:
                self.tasks = {"All": []}
                
            # Ensure All category exists
            if "All" not in self.tasks:
                self.tasks["All"] = []
                
            # Save any new categories that were found
            self.save_categories()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error loading tasks: {e}")
            self.tasks = {"All": []}
    
    def save_tasks(self):
        try:
            # Create a lock file path specific to the operation
            lock_path = TASKS_FILE.with_suffix('.lock')
            
            with FileLock(lock_path):
                # Create backup of existing file
                if TASKS_FILE.exists():
                    backup_file = TASKS_FILE.with_suffix('.backup')
                    import shutil
                    shutil.copy2(TASKS_FILE, backup_file)

                # Ensure all tasks have proper category assignments
                for category in self.categories:
                    if category not in self.tasks:
                        self.tasks[category] = []

                # Save all tasks with their categories
                data = {
                    "version": "1.1",  # Add version for future compatibility
                    "tasks": {
                        "All": self.tasks["All"],
                        **{cat: self.tasks[cat] for cat in self.categories if cat != "All"}
                    }
                }
                
                try:
                    # Validate data with JSON schema
                    jsonschema.validate(instance=data, schema=TASK_SCHEMA)
                except jsonschema.exceptions.ValidationError as ve:
                    messagebox.showerror("Validation Error", f"Task data is invalid: {str(ve)}")
                    return
                
                # Write to temporary file first
                temp_file = TASKS_FILE.with_suffix('.tmp')
                try:
                    with open(temp_file, "w", encoding='utf-8') as file:
                        json.dump(data, file, indent=4, ensure_ascii=False)
                    
                    # Verify the written data
                    with open(temp_file, "r", encoding='utf-8') as file:
                        verify_data = json.load(file)
                    
                    # Only proceed if verification passes
                    if verify_data == data:
                        # Rename temporary file to actual file
                        if TASKS_FILE.exists():
                            TASKS_FILE.unlink()
                        os.rename(temp_file, TASKS_FILE)
                        
                        # Save categories after successful task save
                        self.save_categories()
                        
                        # Remove backup if everything succeeded
                        if backup_file.exists():
                            backup_file.unlink()
                    else:
                        raise Exception("Data verification failed")
                        
                finally:
                    # Clean up temporary file if it exists
                    if temp_file.exists():
                        temp_file.unlink()
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error saving tasks: {e}")
            # Restore from backup if available
            if 'backup_file' in locals() and backup_file.exists():
                try:
                    shutil.copy2(backup_file, TASKS_FILE)
                    messagebox.showinfo("Recovery", "Restored from backup file")
                except Exception as restore_error:
                    messagebox.showerror("Error", f"Error restoring from backup: {restore_error}")
        finally:
            # Clean up lock file
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except:
                pass
    
    def add_task(self, text, category=None, priority="none", bold=None):
        if not text or text == "Add task here":
            return False
            
        category = category or self.current_category
        task = self.create_task(text)
        task["priority"] = priority
        task["bold"] = self._default_bold if bold is None else bold
        
        # Add task to specified category and All category
        if category != "All":
            if category not in task["categories"]:
                task["categories"].append(category)
            
        if category not in self.tasks:
            self.tasks[category] = []
        self.tasks[category].append(task)
        
        if category != "All":
            self.tasks["All"].append(task)
        
        self.save_tasks()
        return True
    
    def move_task_to_category(self, task_id, category):
        # Find task in current category
        current_category = self.current_category
        task = None
        
        # Find task by ID
        for t in self.tasks[current_category]:
            if t["id"] == task_id:
                task = t
                break
                
        if task is None:
            return
            
        # Add category to task's categories list if not already there
        if category not in task["categories"]:
            task["categories"].append(category)
            
            # Add task to new category
            if category not in self.tasks:
                self.tasks[category] = []
            self.tasks[category].append(task)
        
        # Remove from current category if not "All"
        if current_category != "All":
            self.tasks[current_category] = [t for t in self.tasks[current_category] if t["id"] != task_id]
            if current_category in task["categories"]:
                task["categories"].remove(current_category)
        
        # Save changes
        self.save_tasks()
        update_task_display()

    def remove_task_from_category(self, task_id):
        current_category = self.current_category
        if current_category == "All":
            return
            
        # Find task in current category
        for i, task in enumerate(self.tasks[current_category]):
            if task["id"] == task_id:
                # Remove task from current category
                self.tasks[current_category].pop(i)
                # Remove category from task's categories list
                if current_category in task["categories"]:
                    task["categories"].remove(current_category)
                break
        
        # Save changes
        self.save_tasks()
        update_task_display()
    
    def complete_all_tasks(self, category=None):
        category = category or self.current_category
        current_time = datetime.now().isoformat()
        
        # Complete tasks in specified category
        for task in self.tasks[category]:
            if not task["done"]:
                task["done"] = True
                task["completed_time"] = current_time
        
        # If not in "All" category, also update tasks in "All"
        if category != "All":
            for task in self.tasks["All"]:
                if not task["done"]:
                    task["done"] = True
                    task["completed_time"] = current_time
        
        self.save_tasks()
    
    def toggle_task(self, index, category=None):
        category = category or self.current_category
        current_time = datetime.now().isoformat()
        
        # Toggle in current category
        if 0 <= index < len(self.tasks[category]):
            task = self.tasks[category][index]
            task_id = task["id"]
            task["done"] = not task["done"]
            task["completed_time"] = current_time if task["done"] else None
            
            # Update task in all categories
            for cat in task["categories"]:
                if cat in self.tasks:
                    for t in self.tasks[cat]:
                        if t["id"] == task_id:
                            t["done"] = task["done"]
                            t["completed_time"] = task["completed_time"]
            
            self.save_tasks()
    
    def set_task_priority(self, task_id, priority):
        category = self.current_category
        task = None
        
        # Find task by ID
        for t in self.tasks[category]:
            if t["id"] == task_id:
                task = t
                break
                
        if task is None:
            return
            
        # Update priority in all categories
        for cat in task["categories"]:
            if cat in self.tasks:
                for t in self.tasks[cat]:
                    if t["id"] == task_id:
                        t["priority"] = priority
        
        self.save_tasks()
    
    def toggle_task_bold(self, task_id):
        category = self.current_category
        task = None
        
        # Find task by ID in current category
        for t in self.tasks[category]:
            if t["id"] == task_id:
                task = t
                break
                
        if task is None:
            return
            
        task_text = task["text"]
        task_created = task["created_time"]
        
        # Toggle bold in all categories
        for cat, tasks in self.tasks.items():
            for t in tasks:
                if t["text"] == task_text and t["created_time"] == task_created:
                    t["bold"] = not t.get("bold", False)
        
        self.save_tasks()
    
    def edit_task(self, task_id, new_text):
        category = self.current_category
        task = None
        
        # Find task by ID
        for t in self.tasks[category]:
            if t["id"] == task_id:
                task = t
                break
                
        if task is None:
            return False
            
        old_text = task["text"]
        old_created = task["created_time"]
        
        # Update text in all categories
        for cat, tasks in self.tasks.items():
            for t in tasks:
                if t["text"] == old_text and t["created_time"] == old_created:
                    t["text"] = new_text
        
        self.save_tasks()
        return True
    
    def remove_task(self, task_id):
        task_to_remove = None
        category = self.current_category
        
        # Find the task first
        for task in self.tasks[category]:
            if task["id"] == task_id:
                task_to_remove = task
                break
                
        if task_to_remove is None:
            return False
            
        # Remove from all categories
        for cat in list(task_to_remove["categories"]):
            if cat in self.tasks:
                self.tasks[cat] = [t for t in self.tasks[cat] if t["id"] != task_id]
                
        self.save_tasks()
        update_task_display()
        return True

    def get_tasks(self, category=None):
        category = category or self.current_category
        if category not in self.tasks:
            self.tasks[category] = []
        return [self.normalize_task(task) for task in self.tasks[category]]

# Theme management class
class ThemeManager:
    def __init__(self):
        self.current_theme = "light"
        self.themes = {
            "light": {
                "bg": "#ffffff",         # Pure white background
                "fg": "#1a1a1a",         # Near black text
                "accent": "#e3f2fd",     # Lighter blue accent
                "button_bg": "#1976d2",  # Darker blue buttons
                "button_fg": "#ffffff",  # White button text
                "highlight": "#1565c0",  # Deep blue
                "completed": "#2e7d32",  # Darker green
                "sidebar_bg": "#f5f5f5", # Light gray sidebar
                "sidebar_fg": "#1a1a1a", # Near black sidebar text
                "sidebar_button": "#1976d2",  # Darker blue sidebar buttons
                "separator": "#e0e0e0",   # Medium gray separator
                "empty_message": "#757575",  # Darker gray message
                "task_bg": "#ffffff",    # White task background
                "task_hover": "#f5f5f5", # Light gray hover
                "entry_bg": "#ffffff",   # White entry background
                "entry_fg": "#1a1a1a"    # Near black text for entries
            },
            "dark": {
                "bg": "#1a1a1a",         # Dark background
                "fg": "#ecf0f1",         # Light gray text
                "accent": "#2d2d2d",     # Slightly lighter dark
                "button_bg": "#3498db",  # Keep bright blue
                "button_fg": "#ffffff",  # White text
                "highlight": "#2196F3",  # Material blue
                "completed": "#2ecc71",  # Bright green
                "sidebar_bg": "#2c3e50", # Dark blue-gray
                "sidebar_fg": "#ecf0f1", # Light text
                "sidebar_button": "#3498db",  # Bright blue
                "separator": "#34495e",   # Medium blue-gray
                "empty_message": "#7f8c8d",  # Medium gray
                "task_bg": "#2d2d2d",    # Slightly lighter than bg
                "task_hover": "#34495e",  # Blue-gray hover
                "entry_bg": "#2d2d2d",   # Dark entry background
                "entry_fg": "#ecf0f1"    # Light entry text
            }
        }
        self.load_theme_preferences()

    def save_theme_preferences(self):
        try:
            with open(THEME_FILE, "w", encoding='utf-8') as f:
                json.dump({
                    "current_theme": self.current_theme,
                    "themes": self.themes
                }, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Error saving theme preferences: {e}")

    def load_theme_preferences(self):
        try:
            if THEME_FILE.exists():
                with open(THEME_FILE, "r", encoding='utf-8') as f:
                    prefs = json.load(f)
                    self.current_theme = prefs.get("current_theme", "light")
                    saved_themes = prefs.get("themes", {})
                    for theme_name in ["light", "dark"]:
                        if theme_name in saved_themes:
                            self.themes[theme_name].update(saved_themes[theme_name])
        except Exception as e:
            messagebox.showerror("Error", f"Error loading theme preferences: {e}")

    def apply_theme(self):
        theme = self.themes[self.current_theme]
        
        # Configure ttk style for scrollbar
        style = ttk.Style()
        style.configure("Custom.Vertical.TScrollbar",
                       background=theme["bg"],
                       troughcolor=theme["bg"],
                       arrowcolor=theme["fg"])
        scrollbar.configure(style="Custom.Vertical.TScrollbar")
        
        # Update main window and frames
        root.configure(bg=theme["bg"])
        main_frame.configure(bg=theme["bg"])
        entry_frame.configure(bg=theme["bg"])
        task_list_frame.configure(bg=theme["task_bg"])
        task_frame.configure(bg=theme["task_bg"])
        canvas.configure(bg=theme["task_bg"])
        
        # Update entry and text colors
        task_entry.configure(
            bg=theme["entry_bg"],
            fg=theme["entry_fg"],
            insertbackground=theme["entry_fg"],  # Cursor color
            disabledbackground=theme["entry_bg"],
            disabledforeground=theme["empty_message"]
        )
        
        # Update buttons
        add_task_button.configure(
            bg=theme["button_bg"],
            fg=theme["button_fg"],
            activebackground=theme["highlight"],
            activeforeground=theme["button_fg"]
        )
        
        complete_all_button.configure(
            bg="#27ae60",  # Keep green color
            fg="white",
            activebackground="#219a52",
            activeforeground="white"
        )
        
        # Update sidebar
        sidebar_frame.configure(bg=theme["sidebar_bg"])
        sidebar_title.configure(
            bg=theme["sidebar_bg"],
            fg=theme["sidebar_fg"]
        )
        category_frame.configure(bg=theme["sidebar_bg"])
        
        # Update category buttons
        for btn in category_frame.winfo_children():
            if isinstance(btn, ModernButton):
                is_selected = btn.cget("text") == task_manager.current_category
                btn.configure(
                    bg=theme["highlight"] if is_selected else theme["sidebar_button"],
                    fg=theme["button_fg"],
                    activebackground=theme["accent"],
                    activeforeground=theme["button_fg"]
                )
        
        # Update time label and floating button
        time_label.configure(
            bg=theme["sidebar_bg"],
            fg=theme["sidebar_fg"]
        )
        
        # Update floating button if it exists
        for widget in root.winfo_children():
            if isinstance(widget, tk.Button) and widget.cget("text") == "🔧":
                widget.configure(
                    bg=theme["sidebar_bg"],
                    fg=theme["sidebar_fg"],
                    relief="solid",
                    borderwidth=1
                )
                break
        
        # Update task display
        update_task_display()

    def toggle_dark_mode(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()
        self.save_theme_preferences()
        toggle_label = "Light Mode" if self.current_theme == "dark" else "Dark Mode"
        if "Toggle Dark Mode" in [settings_menu.entrycget(i, "label") for i in range(settings_menu.index("end"))]:
            settings_menu.entryconfig(settings_menu.index("Toggle Dark Mode"), label=toggle_label)

# Initialize managers first
task_manager = TaskManager()
theme_manager = ThemeManager()

# Initialize the main window
root = tk.Tk()
root.title("Checklist Manager")
root.geometry("1000x600")

# Function to close the application
def close_application(event):
    root.destroy()

# Bind Alt + F4 to the close_application function
root.bind('<Alt-F4>', close_application)

# Configure root window with margins
root.configure(bg="#f0f0f0")
root.grid_columnconfigure(1, weight=1)  # Content area expands
root.grid_rowconfigure(0, weight=1)

# Create main frames
main_frame = tk.Frame(root, bg="#f0f0f0")
main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_rowconfigure(1, weight=1)

# Create sidebar frame
sidebar_frame = tk.Frame(root, bg="#2c3e50", width=200)
sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
sidebar_frame.grid_propagate(False)

# Sidebar title
sidebar_title = tk.Label(sidebar_frame, text="Categories", 
                        bg="#2c3e50", fg="white",
                        font=("Arial", 12, "bold"))
sidebar_title.grid(row=0, column=0, padx=5, pady=10)

# Category list frame
category_frame = tk.Frame(sidebar_frame, bg="#2c3e50")
category_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

# Task Entry frame
entry_frame = tk.Frame(main_frame, bg="#f0f0f0")
entry_frame.grid(row=0, column=0, pady=(0, 10), sticky="ew")
entry_frame.grid_columnconfigure(0, weight=1)

# Task Entry
task_entry = tk.Entry(entry_frame, font=("Arial", 12))
task_entry.insert(0, "Add task here")
task_entry.config(fg='grey')
task_entry.grid(row=0, column=0, padx=(5, 10), sticky="ew")

# Task list frame
task_list_frame = tk.Frame(main_frame, bg="#ffffff")
task_list_frame.grid(row=1, column=0, sticky="nsew")
task_list_frame.grid_columnconfigure(0, weight=1)
task_list_frame.grid_rowconfigure(0, weight=1)

# Create scrollable frame for tasks
canvas = tk.Canvas(task_list_frame, bg="#ffffff", highlightthickness=0)
scrollbar = ttk.Scrollbar(task_list_frame, orient="vertical", command=canvas.yview)
task_frame = tk.Frame(canvas, bg="#ffffff")

# Configure canvas
canvas.configure(yscrollcommand=scrollbar.set)
canvas.grid(row=0, column=0, sticky="nsew")
scrollbar.grid(row=0, column=1, sticky="ns")

# Create window in canvas for task_frame
canvas_frame = canvas.create_window((0, 0), window=task_frame, anchor="nw")
task_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_frame, width=e.width))

# Create menu bar
menubar = tk.Menu(root)
root.config(menu=menubar)

# File menu
file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Exit", command=root.quit)

# Settings menu
settings_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Settings", menu=settings_menu)

# Help menu
help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Help", menu=help_menu)

# Theme management class
import tkinter as tk
from tkinter import ttk, colorchooser

class ThemeCustomizer:
    def __init__(self, parent, theme_manager):
        self.window = tk.Toplevel(parent)
        self.window.title("Theme Customizer")
        self.window.geometry("500x700")
        self.window.resizable(False, False)
        self.theme_manager = theme_manager

        # Apply current theme
        self.window.configure(bg=theme_manager.themes[theme_manager.current_theme]["bg"])

        # Theme selector frame
        theme_frame = tk.Frame(self.window, 
                               bg=theme_manager.themes[theme_manager.current_theme]["bg"],
                               padx=20, pady=10)
        theme_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        # Theme selector label
        self.select_theme_label = tk.Label(theme_frame, 
                                           text="Select Theme:", 
                                           font=("Arial", 12, "bold"),
                                           bg=theme_manager.themes[theme_manager.current_theme]["bg"],
                                           fg=theme_manager.themes[theme_manager.current_theme]["fg"])
        self.select_theme_label.grid(row=0, column=0, padx=(0,20), sticky="w")

        # **Reset Theme Button**
        self.reset_button = ModernButton(theme_frame, 
                                         text="Reset Colors", 
                                         command=self.reset_theme,
                                         bg=theme_manager.themes[theme_manager.current_theme]["button_bg"],
                                         fg=theme_manager.themes[theme_manager.current_theme]["button_fg"])
        self.reset_button.grid(row=0, column=1, padx=10, sticky="w")

        # Scrollable frame for color pickers
        canvas = tk.Canvas(self.window, 
                           bg=theme_manager.themes[theme_manager.current_theme]["bg"],
                           highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        self.color_frame = tk.Frame(canvas, 
                                    bg=theme_manager.themes[theme_manager.current_theme]["bg"])

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=1, column=0, padx=(20,0), sticky="nsew")
        scrollbar.grid(row=1, column=1, padx=(0,20), sticky="ns")

        # Create window in canvas for color frame
        canvas_frame = canvas.create_window((0,0), window=self.color_frame, anchor="nw")
        self.color_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_frame, width=e.width))

        # Create color pickers
        self.color_frames = {}
        self.create_color_pickers()

        # Bind theme update
        self.window.bind("<FocusIn>", self.update_window_theme)

    def reset_theme(self):
        """Resets the current theme to default settings."""
        if messagebox.askyesno("Reset Theme", "Are you sure you want to reset the current theme to default?"):
            current = self.theme_manager.current_theme
            default_themes = {
                "light": {
                    "bg": "#f5f6f7", "fg": "#2c3e50", "accent": "#e8f0fe",
                    "button_bg": "#3498db", "button_fg": "#ffffff",
                    "highlight": "#2196F3", "completed": "#27ae60",
                    "sidebar_bg": "#e9ecef", "sidebar_fg": "#2c3e50",
                    "sidebar_button": "#3498db", "separator": "#dee2e6",
                    "empty_message": "#95a5a6", "task_bg": "#ffffff",
                    "task_hover": "#f8f9fa", "entry_bg": "#ffffff",
                    "entry_fg": "#2c3e50"
                },
                "dark": {
                    "bg": "#1a1a1a", "fg": "#ecf0f1", "accent": "#2d2d2d",
                    "button_bg": "#3498db", "button_fg": "#ffffff",
                    "highlight": "#2196F3", "completed": "#2ecc71",
                    "sidebar_bg": "#2c3e50", "sidebar_fg": "#ecf0f1",
                    "sidebar_button": "#3498db", "separator": "#34495e",
                    "empty_message": "#7f8c8d", "task_bg": "#2d2d2d",
                    "task_hover": "#34495e", "entry_bg": "#2d2d2d",
                    "entry_fg": "#ecf0f1"
                }
            }
            self.theme_manager.themes[current] = default_themes[current]
            self.theme_manager.apply_theme()
            self.theme_manager.save_theme_preferences()
            self.update_window_theme()
            self.update_color_buttons()

    def update_window_theme(self, event=None):
        """Updates all UI elements to match the current theme."""
        theme = self.theme_manager.themes.get(self.theme_manager.current_theme, {})
        if not theme:
            return

        self.window.configure(bg=theme.get("bg", "#FFFFFF"))

        for widget in self.window.winfo_children():
            if isinstance(widget, (tk.Frame, tk.Label)):
                widget.configure(bg=theme.get("bg", "#FFFFFF"))
                if isinstance(widget, tk.Label):
                    widget.configure(fg=theme.get("fg", "#000000"))
            elif isinstance(widget, tk.Canvas):
                widget.configure(bg=theme.get("bg", "#FFFFFF"))

        # Update reset button colors
        self.reset_button.configure(bg=theme.get("button_bg", "#3498db"),
                                    fg=theme.get("button_fg", "#ffffff"))

        # Update color frame
        if hasattr(self, "color_frame") and self.color_frame:
            self.color_frame.configure(bg=theme.get("bg", "#FFFFFF"))
            for frame in self.color_frame.winfo_children():
                frame.configure(bg=theme.get("bg", "#FFFFFF"))
                for child in frame.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(bg=theme.get("bg", "#FFFFFF"), fg=theme.get("fg", "#000000"))
                    elif isinstance(child, ModernColorButton):
                        child.update_colors()

    def update_color_buttons(self):
        """Updates all color preview buttons to match the current theme."""
        theme = self.theme_manager.themes[self.theme_manager.current_theme]
        for key, (preview, color_var) in self.color_frames.items():
            preview.configure(bg=theme[key])
            color_var.set(theme[key])

    def pick_color(self, key, color_var):
        """Opens a color chooser dialog and updates the corresponding color variable."""
        color = colorchooser.askcolor(title=f"Choose {key.replace('_', ' ').title()} Color")
        if color[1]:  # If a color was chosen
            color_var.set(color[1])  # Update the color variable
            # Update the color preview
            preview, _ = self.color_frames[key]
            preview.configure(bg=color[1])
            # Optionally, update the theme manager with the new color
            self.theme_manager.themes[self.theme_manager.current_theme][key] = color[1]
            self.theme_manager.apply_theme()  # Apply the new theme
            self.theme_manager.save_theme_preferences()  # Save the new preferences
            self.update_window_theme()  # Refresh the UI

    def create_color_pickers(self):
        elements = {
            "bg": "Background Color",
            "fg": "Text Color",
            "accent": "Accent Color",
            "button_bg": "Button Background",
            "button_fg": "Button Text",
            "highlight": "Highlight Color",
            "completed": "Completed Task Color",
            "sidebar_bg": "Sidebar Background",
            "sidebar_fg": "Sidebar Text",
            "sidebar_button": "Sidebar Button",
            "separator": "Separator Color",
            "empty_message": "Empty Message Color",
            "task_bg": "Task Background",
            "task_hover": "Task Hover Color",
            "entry_bg": "Entry Background",
            "entry_fg": "Entry Text"
        }
        
        for key, label in elements.items():
            frame = tk.Frame(self.color_frame, 
                             bg=self.theme_manager.themes[self.theme_manager.current_theme]["bg"])
            frame.grid(row=len(self.color_frame.winfo_children()), column=0, padx=5, pady=5, sticky="ew")
            
            # Color preview button on the left
            preview = tk.Frame(frame, width=30, height=20, relief="solid", borderwidth=1)
            preview.grid(row=0, column=0, padx=5, sticky="w")
            preview.pack_propagate(False)
            
            # Label on the right
            tk.Label(frame, 
                     text=label + ":", 
                     font=("Arial", 9),
                     bg=self.theme_manager.themes[self.theme_manager.current_theme]["bg"],
                     fg=self.theme_manager.themes[self.theme_manager.current_theme]["fg"]).grid(row=0, column=1, padx=5, sticky="w")
            
            # Current color value
            color_var = tk.StringVar()
            color_entry = tk.Entry(frame, 
                                   textvariable=color_var,
                                   width=10,
                                   bg=self.theme_manager.themes[self.theme_manager.current_theme]["entry_bg"],
                                   fg=self.theme_manager.themes[self.theme_manager.current_theme]["entry_fg"],
                                   insertbackground=self.theme_manager.themes[self.theme_manager.current_theme]["entry_fg"])
            color_entry.grid(row=0, column=2, padx=5, sticky="w")
            
            # Color picker button
            pick_button = ModernColorButton(frame,
                                            text="Choose",
                                            command=lambda k=key, v=color_var: self.pick_color(k, v))
            pick_button.grid(row=0, column=3, padx=5, sticky="w")
            
            self.color_frames[key] = (preview, color_var)
    
        self.update_color_buttons()

    def apply_changes(self):
        self.theme_manager.save_theme_preferences()
        messagebox.showinfo("Success", "Theme changes applied and saved successfully!")

def show_theme_customizer():
    ThemeCustomizer(root, theme_manager)

# Task menu functions
def show_task_menu(event, task_id):
    menu = tk.Menu(root)
    
    # Find task by ID
    task = None
    for t in task_manager.tasks[task_manager.current_category]:
        if t["id"] == task_id:
            task = t
            break
            
    if not task:
        return
    
    # Edit task option
    menu.add_command(label="✏️ Edit", command=lambda: edit_task_dialog(task["id"]))
    menu.add_separator()
    
    # Priority submenu
    priority_menu = tk.Menu(menu)
    priorities = [("High", "high", "🔴"), ("Medium", "medium", "🟡"), ("Low", "low", "🟢"), ("None", "none", "⚪")]
    for label, value, icon in priorities:
        priority_menu.add_command(
            label=f"{icon} {label}",
            command=lambda p=value: task_manager.set_task_priority(task["id"], p))
    menu.add_cascade(label="🎯 Priority", menu=priority_menu)
    
    # Category management
    if task_manager.current_category != "All":
        menu.add_command(
            label="🗑️ Remove from Category",
            command=lambda: task_manager.remove_task_from_category(task["id"])
        )
    
    category_menu = tk.Menu(menu)
    for category in task_manager.categories:
        if category != task_manager.current_category and category != "All":
            category_menu.add_command(
                label=category,
                command=lambda c=category: task_manager.move_task_to_category(task["id"], c)
            )
    if len(task_manager.categories) > 2:  # More than just "All" and current category
        menu.add_cascade(label="📁 Move to Category", menu=category_menu)
    
    # Text formatting
    menu.add_separator()
    menu.add_command(
        label="🅱️ Toggle Bold",
        command=lambda: task_manager.toggle_task_bold(task["id"])
    )
    
    # Delete task
    menu.add_separator()
    menu.add_command(
        label="❌ Delete Task",
        command=lambda: delete_task(task["id"])
    )
    
    # Show menu at event position
    menu.tk_popup(event.x_root, event.y_root)
    update_task_display()

def edit_task_dialog(task_id):
    task = None
    for t in task_manager.tasks[task_manager.current_category]:
        if t["id"] == task_id:
            task = t
            break
            
    if task is None:
        return
        
    new_task_text = simpledialog.askstring("Edit Task", 
                                         "Edit the task:",
                                         initialvalue=task["text"])
    if new_task_text and new_task_text.strip():
        task_manager.edit_task(task_id, new_task_text.strip())
        update_task_display()

def delete_task(task_id):
    tasks = task_manager.get_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task and messagebox.askyesno("Confirm", f"Are you sure you want to remove this task?\n\n{task['text']}"):
        task_manager.remove_task(task_id)
        update_task_display()

def remove_selected_task():
    task = task_manager.get_tasks()[selected_task_id]
    if messagebox.askyesno("Confirm", f"Are you sure you want to remove this task?\n\n{task['text']}"):
        task_manager.remove_task(selected_task_id)
        update_task_display()

def set_priority(priority):
    task_manager.set_task_priority(selected_task_id, priority)
    update_task_display()

def toggle_bold():
    task_manager.toggle_task_bold(selected_task_id)
    update_task_display()

def edit_selected_task():
    if not hasattr(task_menu, 'task_id'):
        return
    task_id = task_menu.task_id
    tasks = task_manager.get_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task:
        new_task_text = simpledialog.askstring("Edit Task", 
                                             "Edit the task:",
                                             initialvalue=task["text"])
        if new_task_text and new_task_text.strip():
            task_manager.edit_task(task_id, new_task_text.strip())
            update_task_display()

# Create right-click menu
task_menu = tk.Menu(root, tearoff=0)
task_menu.add_command(label="Edit Task", command=edit_selected_task)

# Add Priority submenu
priority_menu = tk.Menu(task_menu, tearoff=0)
priority_menu.add_command(label="High Priority", 
                        command=lambda: set_priority("high"),
                        foreground=task_manager.PRIORITY_SYMBOLS["high"])
priority_menu.add_command(label="Medium Priority", 
                        command=lambda: set_priority("medium"),
                        foreground=task_manager.PRIORITY_SYMBOLS["medium"])
priority_menu.add_command(label="Low Priority", 
                        command=lambda: set_priority("low"),
                        foreground=task_manager.PRIORITY_SYMBOLS["low"])
priority_menu.add_command(label="No Priority", 
                        command=lambda: set_priority("none"))
task_menu.add_cascade(label="Set Priority", menu=priority_menu)

# Add Bold toggle
task_menu.add_command(label="Toggle Bold", command=toggle_bold)
task_menu.add_separator()
task_menu.add_command(label="Remove Task", command=remove_selected_task)

# Task functions
def add_task():
    task_text = task_entry.get().strip()
    if task_manager.add_task(task_text):
        update_task_display()
        task_entry.delete(0, tk.END)
        task_entry.insert(0, "Add task here")
        task_entry.config(fg='grey')
        root.focus_set()  # Remove focus from entry
    else:
        messagebox.showwarning("Warning", "Task cannot be empty!")

def toggle_task(index):
    task_manager.toggle_task(index)
    update_task_display()

# Update task display function
def update_task_display():
    # Clear existing tasks
    for widget in task_frame.winfo_children():
        widget.destroy()
    
    # Get tasks for current page
    tasks = task_manager.get_current_page_tasks()
    if not tasks:
        # Show "No tasks" message
        no_tasks_label = tk.Label(task_frame, 
                                text="No tasks in this category",
                                bg=theme_manager.themes[theme_manager.current_theme]["task_bg"],
                                fg=theme_manager.themes[theme_manager.current_theme]["empty_message"],
                                font=("Arial", 11))
        no_tasks_label.grid(row=0, column=0, padx=20, pady=20)
        update_pagination_controls()
        return

    task_frame.grid_columnconfigure(0, weight=1)  # Allow the first column to expand

    for i, task in enumerate(tasks):
        task_row = tk.Frame(task_frame, 
                          bg=theme_manager.themes[theme_manager.current_theme]["task_bg"])
        task_row.grid(row=i*2, column=0, padx=10, pady=2, sticky="nsew")  # Use sticky="nsew" to stretch horizontally and vertically

        # Add hover effect
        def on_enter(e, row=task_row):
            row.configure(bg=theme_manager.themes[theme_manager.current_theme]["task_hover"])
            for child in row.winfo_children():
                child.configure(bg=theme_manager.themes[theme_manager.current_theme]["task_hover"])
                
        def on_leave(e, row=task_row):
            row.configure(bg=theme_manager.themes[theme_manager.current_theme]["task_bg"])
            for child in row.winfo_children():
                child.configure(bg=theme_manager.themes[theme_manager.current_theme]["task_bg"])
        
        task_row.bind("<Enter>", on_enter)
        task_row.bind("<Leave>", on_leave)
        
        # Checkbox with improved visibility and margins
        var = tk.BooleanVar(value=task["done"])
        cb = tk.Checkbutton(task_row, 
                           variable=var,
                           bg=theme_manager.themes[theme_manager.current_theme]["task_bg"],
                           activebackground=theme_manager.themes[theme_manager.current_theme]["task_bg"],
                           command=lambda idx=i: toggle_task(idx),
                           indicatoron=False,  # Disable default indicator
                           selectcolor=theme_manager.themes[theme_manager.current_theme]["task_bg"],
                           width=2,
                           height=1,
                           text="✓" if task["done"] else "",  # Show checkmark when done
                           font=("Arial", 10),
                           relief="solid",
                           borderwidth=1,
                           offrelief="solid",
                           fg=theme_manager.themes[theme_manager.current_theme]["completed"],
                           padx=5,
                           pady=2)
        cb.grid(row=0, column=0, padx=(5, 10), pady=2)
        
        # Task text with timestamp and priority
        text_color = theme_manager.themes[theme_manager.current_theme]["completed"] if task["done"] else theme_manager.themes[theme_manager.current_theme]["fg"]
        
        # Create task text with priority symbol
        task_text = task["text"]
        priority_symbol = task_manager.PRIORITY_SYMBOLS[task["priority"]]
        if priority_symbol:
            task_text = f"{task_text} {priority_symbol}"
            
        font = ("Arial", 11, "bold") if task["bold"] else ("Arial", 11)
            
        task_label = tk.Label(task_row, 
                            text=task_text,
                            bg=theme_manager.themes[theme_manager.current_theme]["task_bg"],
                            fg=text_color,
                            font=font,
                            anchor="w")
        task_label.grid(row=0, column=1, sticky="w", padx=5)
        task_label.bind("<Button-3>", lambda e, id=task["id"]: show_task_menu(e, id))
        
        # Add timestamp label
        created_time = datetime.fromisoformat(task['created_time'])
        if time_format_24_hour:
            formatted_created_time = created_time.strftime('%H:%M')  # 24-hour format
        else:
            formatted_created_time = created_time.strftime('%I:%M %p')  # 12-hour format
        
        timestamp_text = f"Created: {formatted_created_time}"

        if task["done"] and task["completed_time"]:
            completion_time = datetime.fromisoformat(task["completed_time"])
            if completion_time.date() != datetime.now().date():
                if time_format_24_hour:
                    formatted_completed_time = completion_time.strftime('%Y-%m-%d %H:%M')  # 24-hour format
                else:
                    formatted_completed_time = completion_time.strftime('%Y-%m-%d %I:%M %p')  # 12-hour format
            else:
                if time_format_24_hour:
                    formatted_completed_time = completion_time.strftime('%H:%M')  # 24-hour format
                else:
                    formatted_completed_time = completion_time.strftime('%I:%M %p')  # 12-hour format
            timestamp_text += f"\nCompleted: {formatted_completed_time}"
            
        timestamp_label = tk.Label(task_row,
                                 text=timestamp_text,
                                 bg=theme_manager.themes[theme_manager.current_theme]["task_bg"],
                                 fg=theme_manager.themes[theme_manager.current_theme]["empty_message"],
                                 font=("Arial", 8),
                                 justify="right")
        timestamp_label.grid(row=0, column=2, padx=5)
        
        # Make the entire row clickable for toggling and right-click
        for widget in [task_row, task_label, timestamp_label]:
            widget.bind("<Button-1>", lambda e, idx=i: toggle_task(idx))
            widget.bind("<Enter>", lambda e, row=task_row: on_enter(e, row))
            widget.bind("<Leave>", lambda e, row=task_row: on_leave(e, row))
            widget.bind("<Button-3>", lambda e, id=task["id"]: show_task_menu(e, id))
        
        # Create a separator
        separator = tk.Frame(task_frame, height=1, bg=theme_manager.themes[theme_manager.current_theme]["separator"])
        separator.grid(row=i*2+1, column=0, padx=5, pady=1, sticky="ew")  # Use sticky="ew" to stretch horizontally

def edit_task_dialog(task_id):
    task = None
    for t in task_manager.tasks[task_manager.current_category]:
        if t["id"] == task_id:
            task = t
            break
            
    if task is None:
        return
        
    new_task_text = simpledialog.askstring("Edit Task", 
                                         "Edit the task:",
                                         initialvalue=task["text"])
    if new_task_text and new_task_text.strip():
        task_manager.edit_task(task_id, new_task_text.strip())
        update_task_display()

def complete_all_tasks():
    if messagebox.askyesno("Complete All", "Are you sure you want to complete all tasks in this category?"):
        task_manager.complete_all_tasks()
        update_task_display()

# Entry field functions
def on_entry_click(event):
    if task_entry.get() == "Add task here":
        task_entry.delete(0, tk.END)
        task_entry.config(fg=theme_manager.themes[theme_manager.current_theme]["entry_fg"])

def on_focus_out(event):
    if task_entry.get() == "":
        task_entry.insert(0, "Add task here")
        task_entry.config(fg=theme_manager.themes[theme_manager.current_theme]["empty_message"])
    root.unbind("<Key>")
    root.focus_set()

def on_entry_focus(event):
    root.bind("<Key>", lambda e: "break" if task_entry.focus_get() is None else None)

# Bind entry field events
task_entry.bind('<FocusIn>', lambda e: (on_entry_click(e), on_entry_focus(e)))
task_entry.bind('<FocusOut>', on_focus_out)
task_entry.bind('<Return>', lambda e: add_task())

# Variable to track the current time format (12-hour or 24-hour)
time_format_24_hour = True  # Default to 24-hour format

# Load time format preferences
if TIME_FORMAT_FILE.exists():
    with open(TIME_FORMAT_FILE, "r", encoding='utf-8') as f:
        prefs = json.load(f)
        time_format_24_hour = prefs.get("time_format_24_hour", True)

# Function to toggle time format
def toggle_time_format():
    global time_format_24_hour
    time_format_24_hour = not time_format_24_hour  # Toggle the format
    save_time_format_preferences()  # Save the preference
    update_time_display()  # Update the display immediately
    
def save_time_format_preferences():
    with open(TIME_FORMAT_FILE, 'w') as f:
        json.dump({"time_format_24_hour": time_format_24_hour}, f)

# Function to update the displayed time based on the selected format
def update_time_display():
    current_time = datetime.now()
    if time_format_24_hour:
        formatted_time = current_time.strftime('%H:%M')  # 24-hour format
    else:
        formatted_time = current_time.strftime('%I:%M %p')  # 12-hour format
    # Update your UI element that shows the time with formatted_time
    time_label.config(text=formatted_time)  # Assuming you have a label for displaying time


# Add time label
time_label = tk.Label(root, text="", font=("Arial", 12))
time_label.configure(
    relief="solid",
    borderwidth=1,
    padx=10,
    pady=5,
    bg=theme_manager.themes[theme_manager.current_theme]["sidebar_bg"],  # Use sidebar background for better visibility
    fg=theme_manager.themes[theme_manager.current_theme]["sidebar_fg"]   # Use sidebar text color for better contrast
)
time_label.grid(row=999, column=0, sticky="sw", padx=15, pady=10)  # Using a high row number to ensure it's at the bottom

# Update time display
update_time_display()

# Add time format toggle button
def create_floating_button():
    floating_button = tk.Button(root, text='🔧', font=("Arial", 16), borderwidth=1)
    floating_button.place(relx=0.95, rely=0.95, anchor='se')  # Bottom right corner

    # Create popup menu
    popup_menu = tk.Menu(root, tearoff=0)
    popup_menu.add_command(label="Toggle Dark/Light Mode", command=lambda: theme_manager.toggle_dark_mode())
    popup_menu.add_command(label="Toggle Time Format", command=toggle_time_format)
    popup_menu.add_separator()
    popup_menu.add_checkbutton(label="Bold New Tasks", command=lambda: toggle_default_bold())

    def show_popup(event=None):
        popup_menu.post(floating_button.winfo_rootx(), floating_button.winfo_rooty() - popup_menu.winfo_reqheight())

    # Bind hover events to show/hide menu
    floating_button.bind("<Enter>", lambda e: (floating_button.configure(bg=theme_manager.themes[theme_manager.current_theme]["button_bg"], fg=theme_manager.themes[theme_manager.current_theme]["button_fg"]), show_popup()))
    floating_button.bind("<Leave>", lambda e: (floating_button.configure(bg=theme_manager.themes[theme_manager.current_theme]["sidebar_bg"], fg=theme_manager.themes[theme_manager.current_theme]["sidebar_fg"]), popup_menu.unpost()))
    popup_menu.bind("<Leave>", lambda e: popup_menu.unpost())

    # Configure initial colors
    floating_button.configure(
        bg=theme_manager.themes[theme_manager.current_theme]["sidebar_bg"],
        fg=theme_manager.themes[theme_manager.current_theme]["sidebar_fg"],
        relief="solid"
    )

def toggle_default_bold():
    is_bold = task_manager.toggle_default_bold()
    # Removed the messagebox.showinfo call here

# Call this function at the end of your main setup code
create_floating_button()

# Settings menu
settings_menu.add_command(label="Customize Theme", command=show_theme_customizer)
settings_menu.add_command(label="Toggle Dark/Light Mode", command=lambda: theme_manager.toggle_dark_mode())
settings_menu.add_command(label="Toggle Time Format", command=toggle_time_format)

# Configure alt-key access
root.option_add('*tearOff', False)  # Disable tear-off menus
menubar.bind_all('<Alt-Key>', lambda e: menubar.focus_set())

# Add Task Button with modern style
add_task_button = ModernButton(entry_frame, 
                           text="Add Task",
                           command=lambda: add_task(),
                           bg="#d0d0d0", 
                           fg="black",
                           font=("Arial", 10))
add_task_button.grid(row=0, column=1, padx=(0, 5))

# Add Complete All button
complete_all_button = ModernButton(entry_frame, 
                               text="Complete All",
                               command=lambda: complete_all_tasks(),
                               bg="#27ae60",  # Green color
                               fg="white",
                               font=("Arial", 10))
complete_all_button.grid(row=0, column=2, padx=5)

# Add category button with modern style
add_category_button = ModernButton(sidebar_frame, 
                              text="+ Add Category",
                              bg="#34495e", 
                              fg="white",
                              font=("Arial", 10),
                              command=lambda: add_category())
add_category_button.grid(row=2, column=0, padx=5, pady=10, sticky="ew")

# Create category dropdown
category_var = tk.StringVar(value="All Tasks")
category_dropdown = ttk.Combobox(category_frame, textvariable=category_var, state="readonly")
category_dropdown.grid(row=0, column=0, padx=5, pady=(0, 5), sticky="ew")

def update_category_dropdown():
    categories = task_manager.categories
    category_dropdown['values'] = categories
    category_dropdown.set(task_manager.current_category)

# Bind category selection
category_dropdown.bind('<<ComboboxSelected>>', lambda e: switch_category(category_var.get()))
update_category_dropdown()

# Category functions
def switch_category(category_name):
    task_manager.current_category = category_name
    # Update category buttons to show which is selected
    for btn in category_frame.winfo_children():
        if isinstance(btn, ModernButton):
            if btn.cget("text") == category_name:
                btn.configure(bg="#2980b9")  # Highlight selected category
            else:
                btn.configure(bg="#34495e")  # Reset others
    update_task_display()

def add_category():
    new_category = simpledialog.askstring("Add Category", "Enter new category name:")
    if new_category:
        if new_category in task_manager.tasks:
            messagebox.showwarning("Warning", f"Category '{new_category}' already exists!")
            return
            
        # Create category button
        category_btn = ModernButton(category_frame, 
                                  text=new_category,
                                  bg="#34495e", 
                                  fg="white",
                                  font=("Arial", 10),
                                  command=lambda n=new_category: switch_category(n))
        category_btn.grid(row=len(category_frame.winfo_children()), column=0, padx=5, pady=2, sticky="ew")
        
        # Initialize empty task list for new category
        task_manager.tasks[new_category] = []
        task_manager.save_tasks()  # Save tasks
        task_manager.save_categories()  # Save the new category to categories.json
        switch_category(new_category)

def complete_all_tasks():
    if messagebox.askyesno("Complete All", "Are you sure you want to complete all tasks in this category?"):
        task_manager.complete_all_tasks()
        update_task_display()

# Category right-click menu
def show_category_menu(event, category):
    menu = tk.Menu(root)
    
    if category != "All":
        menu.add_command(label="✏️ Edit", command=lambda: edit_category_dialog(category))
        menu.add_separator()
        menu.add_command(label="❌ Delete", command=lambda: delete_category(category))
    
    menu.tk_popup(event.x_root, event.y_root)

def edit_category_dialog(category):
    new_name = simpledialog.askstring("Edit Category", "Enter new category name:", initialvalue=category)
    if new_name and new_name.strip() and new_name != category:
        if new_name not in task_manager.categories:
            task_manager.tasks[new_name] = task_manager.tasks.pop(category)
            task_manager.categories[task_manager.categories.index(category)] = new_name
            task_manager.save_tasks()
            task_manager.save_categories()
            update_category_buttons()
            update_category_dropdown()
        else:
            messagebox.showwarning("Warning", f"Category '{new_name}' already exists!")

def delete_category(category):
    if category == "All":
        messagebox.showwarning("Warning", "Cannot delete the 'All' category!")
        return
        
    if messagebox.askyesno("Delete Category", f"Are you sure you want to delete the category '{category}'?"):
        task_manager.tasks.pop(category)
        task_manager.categories.remove(category)
        task_manager.save_tasks()
        task_manager.save_categories()
        if task_manager.current_category == category:
            task_manager.current_category = "All"
        update_category_buttons()
        update_category_dropdown()
        update_task_display()

def remove_category():
    category_to_remove = category_var.get()
    
    if not category_to_remove or category_to_remove == "All":
        messagebox.showwarning("Warning", "Cannot remove the 'All' category!")
        return
        
    if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the category '{category_to_remove}'?\nAll tasks in this category will be moved to 'All'."):
        # Move tasks to 'All' category
        for task in task_manager.tasks[category_to_remove]:
            task["categories"].remove(category_to_remove)
            if task not in task_manager.tasks["All"]:
                task_manager.tasks["All"].append(task)
        
        # Remove category
        del task_manager.tasks[category_to_remove]
        task_manager.categories.remove(category_to_remove)
        
        # Save changes
        task_manager.save_categories()
        task_manager.save_tasks()
        
        # Update UI
        category_var.set("All")
        update_category_dropdown()
        update_category_buttons()
        update_task_display()

# Create category menu
category_menu = tk.Menu(root, tearoff=0)
category_menu.add_command(label="Add Category", command=add_category)
category_menu.add_command(label="Edit Category", command=lambda: edit_category(category_var.get()))
category_menu.add_command(label="Remove Category", command=lambda: remove_category())

# Category buttons frame
category_buttons_frame = tk.Frame(root, bg=theme_manager.themes[theme_manager.current_theme]["bg"])
category_buttons_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=5)

# Add Category button
add_category_btn = ModernButton(
    category_buttons_frame,
    text="Add Category",
    command=add_category,
    bg=theme_manager.themes[theme_manager.current_theme]["button_bg"],
    fg=theme_manager.themes[theme_manager.current_theme]["button_fg"]
)
add_category_btn.pack(side=tk.LEFT, padx=5)

# Edit Category button
edit_category_btn = ModernButton(
    category_buttons_frame,
    text="Edit Category",
    command=lambda: edit_category(category_var.get()),
    bg=theme_manager.themes[theme_manager.current_theme]["button_bg"],
    fg=theme_manager.themes[theme_manager.current_theme]["button_fg"]
)
edit_category_btn.pack(side=tk.LEFT, padx=5)

# Remove Category button
remove_category_btn = ModernButton(
    category_buttons_frame,
    text="Remove Category",
    command=lambda: remove_category(),
    bg=theme_manager.themes[theme_manager.current_theme]["button_bg"],
    fg=theme_manager.themes[theme_manager.current_theme]["button_fg"]
)
remove_category_btn.pack(side=tk.LEFT, padx=5)

def update_category_buttons():
    # Clear existing category buttons
    for widget in category_frame.winfo_children():
        widget.destroy()
    
    # Create category dropdown
    category_var = tk.StringVar(value=task_manager.current_category)
    category_dropdown = ttk.Combobox(category_frame, textvariable=category_var, state="readonly")
    category_dropdown['values'] = task_manager.categories
    category_dropdown.set(task_manager.current_category)
    category_dropdown.grid(row=0, column=0, padx=5, pady=(0, 5), sticky="ew")
    category_dropdown.bind('<<ComboboxSelected>>', lambda e: switch_category(category_var.get()))
    
    # Recreate category buttons
    for category in task_manager.categories:
        btn = ModernButton(category_frame,
                          text=category,
                          bg="#34495e", 
                          fg="white",
                          font=("Arial", 10, "bold") if category == "All" else ("Arial", 10),
                          command=lambda c=category: switch_category(c))
        btn.grid(row=len(category_frame.winfo_children()), column=0, padx=5, pady=(0, 5), sticky="ew")
        
        # Add right-click menu
        btn.bind("<Button-3>", lambda e, c=category: show_category_menu(e, c))

# Pagination frame
pagination_frame = tk.Frame(root, bg=theme_manager.themes[theme_manager.current_theme]["bg"])
pagination_frame.grid(row=4, column=0, columnspan=2, pady=10, sticky="ew")

def update_pagination_controls():
    total_pages = task_manager.get_total_pages()
    current_page = task_manager.current_page
    
    # Update page info label
    if total_pages > 0:
        page_info.config(text=f"Page {current_page + 1} of {total_pages}")
        prev_page_btn.config(state="normal" if current_page > 0 else "disabled")
        next_page_btn.config(state="normal" if current_page < total_pages - 1 else "disabled")
    else:
        page_info.config(text="No pages")
        prev_page_btn.config(state="disabled")
        next_page_btn.config(state="disabled")

def handle_page_change(change_func):
    if change_func():
        update_task_display()
        update_pagination_controls()

# Previous page button
prev_page_btn = ModernButton(
    pagination_frame,
    text="◀",
    command=lambda: handle_page_change(task_manager.prev_page),
    bg=theme_manager.themes[theme_manager.current_theme]["button_bg"],
    fg=theme_manager.themes[theme_manager.current_theme]["button_fg"]
)
prev_page_btn.grid(row=0, column=0, padx=5)

# Page info label
page_info = tk.Label(
    pagination_frame,
    text="Page 1 of 1",
    bg=theme_manager.themes[theme_manager.current_theme]["bg"],
    fg=theme_manager.themes[theme_manager.current_theme]["fg"]
)
page_info.grid(row=0, column=1, padx=10)

# Next page button
next_page_btn = ModernButton(
    pagination_frame,
    text="▶",
    command=lambda: handle_page_change(task_manager.next_page),
    bg=theme_manager.themes[theme_manager.current_theme]["button_bg"],
    fg=theme_manager.themes[theme_manager.current_theme]["button_fg"]
)
next_page_btn.grid(row=0, column=2, padx=5)

# Update pagination controls initially
update_pagination_controls()

# Modify switch_category to reset pagination
def switch_category(category_name):
    if category_name in task_manager.tasks:
        task_manager.current_category = category_name
        task_manager.current_page = 0  # Reset to first page
        update_task_display()
        update_pagination_controls()

# Start the main loop
root.mainloop()