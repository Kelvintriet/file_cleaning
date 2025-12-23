import webview
import os
import sys
import shutil
import time
import threading
import json
import fnmatch
import re
import requests
import nltk
import ssl
import PyPDF2
import docx
import pytesseract
from PIL import Image

# SSL Hack for NLTK download (Mac specific usually)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Download NLTK data
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer

def create_app():
    # Determine the path to the web directory
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    web_dir = os.path.join(base_path, 'web')
    index_path = os.path.join(web_dir, 'index.html')

    # Config for undo history
    config_dir = os.path.join(os.path.expanduser("~"), ".system_cleaner")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    history_file = os.path.join(config_dir, "history.json")
    ignore_file = os.path.join(config_dir, "ignore_list.json")
    include_file = os.path.join(config_dir, "include_list.json")
    settings_file = os.path.join(config_dir, "settings.json")
    # Rules now managed via profiles
    profiles_dir = os.path.join(config_dir, "profiles")
    if not os.path.exists(profiles_dir):
        os.makedirs(profiles_dir)
    
    # Legacy migration: move rules.json to profiles/Default.json if it exists
    legacy_rules_file = os.path.join(config_dir, "rules.json")
    default_profile_file = os.path.join(profiles_dir, "Default.json")
    
    if os.path.exists(legacy_rules_file) and not os.path.exists(default_profile_file):
        try:
            shutil.move(legacy_rules_file, default_profile_file)
        except:
            pass

    ai_config_file = os.path.join(config_dir, "ai_config.json")

    class Api:
        def __init__(self):
            self.stop_cleaning = False
            self.ai_results = []
            
        # --- Profiles Management ---
        def get_profiles(self):
            profiles = []
            try:
                for f in os.listdir(profiles_dir):
                    if f.endswith(".json"):
                        profiles.append(os.path.splitext(f)[0])
            except:
                pass
            if not profiles:
                profiles = ["Default"]
            return sorted(profiles)

        def get_active_profile(self):
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r') as f:
                        settings = json.load(f)
                        profile = settings.get("active_profile", "Default")
                        # Verify it exists
                        if os.path.exists(os.path.join(profiles_dir, f"{profile}.json")):
                            return profile
                except:
                    pass
            return "Default"

        def set_active_profile(self, profile_name):
            settings = {}
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r') as f:
                        settings = json.load(f)
                except:
                    pass
            
            settings["active_profile"] = profile_name
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
            return True

        def create_profile(self, profile_name):
            # Sanitize filename
            safe_name = "".join([c for c in profile_name if c.isalnum() or c in (' ', '-', '_')]).strip()
            if not safe_name:
                return {"error": "Invalid profile name"}
            
            path = os.path.join(profiles_dir, f"{safe_name}.json")
            if os.path.exists(path):
                return {"error": "Profile already exists"}
            
            # Create empty rules
            with open(path, 'w') as f:
                json.dump([], f)
            return {"success": True, "name": safe_name}

        def rename_profile(self, old_name, new_name):
            if old_name == "Default":
                return {"error": "Cannot rename Default profile"}
            
            safe_new_name = "".join([c for c in new_name if c.isalnum() or c in (' ', '-', '_')]).strip()
            if not safe_new_name:
                return {"error": "Invalid new name"}

            old_path = os.path.join(profiles_dir, f"{old_name}.json")
            new_path = os.path.join(profiles_dir, f"{safe_new_name}.json")
            
            if not os.path.exists(old_path):
                return {"error": "Profile not found"}
            if os.path.exists(new_path):
                return {"error": "A profile with this name already exists"}
            
            try:
                os.rename(old_path, new_path)
                
                # Update active profile if needed
                if self.get_active_profile() == old_name:
                    self.set_active_profile(safe_new_name)
                    
                return {"success": True, "new_name": safe_new_name}
            except Exception as e:
                return {"error": str(e)}

        def delete_profile(self, profile_name):
            if profile_name == "Default":
                return {"error": "Cannot delete Default profile"}
            
            path = os.path.join(profiles_dir, f"{profile_name}.json")
            if os.path.exists(path):
                os.remove(path)
                
                # If we deleted the active one, switch to Default
                if self.get_active_profile() == profile_name:
                    self.set_active_profile("Default")
                return {"success": True}
            return {"error": "Profile not found"}
            
        # --- Community (Firebase) ---
        def fetch_community_rules(self, db_url=None):
            """Fetch all rules from a Firebase Realtime DB URL"""
            # Use hardcoded default if not provided
            if not db_url:
                db_url = "https://chat-b31fb-default-rtdb.firebaseio.com/"
            
            # Ensure URL ends with .json
            url = db_url.rstrip('/')
            if not url.endswith('.json'):
                url += '/community_rules.json'
            else:
                # If user provided base url like ...firebaseio.com/
                if not url.endswith('community_rules.json'):
                     url += '/community_rules.json'

            try:
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()
                    # Firebase returns dict with keys, convert to list
                    rules_list = []
                    if data:
                        for key, val in data.items():
                            val['id'] = key
                            rules_list.append(val)
                    return {"success": True, "rules": rules_list}
                elif response.status_code == 401:
                    return {"error": "Permission Denied (401). The database rules block public access. Please update rules in Firebase Console."}
                else:
                    return {"error": f"Failed to fetch: {response.status_code}"}
            except Exception as e:
                return {"error": str(e)}

        def publish_community_rule(self, db_url, rule_data):
            """Publish current profile as a community rule"""
            # Use hardcoded default if not provided
            if not db_url:
                db_url = "https://chat-b31fb-default-rtdb.firebaseio.com/"

             # Ensure URL ends with .json
            url = db_url.rstrip('/')
            if not url.endswith('.json'):
                url += '/community_rules.json'
            
            try:
                # Using POST to auto-generate ID
                response = requests.post(url, json=rule_data)
                if response.status_code == 200:
                    return {"success": True}
                elif response.status_code == 401:
                    return {"error": "Permission Denied (401). Database is read-only or requires auth. Update Firebase Rules."}
                else:
                    return {"error": f"Failed to publish: {response.status_code}"}
            except Exception as e:
                return {"error": str(e)}

        def install_community_rule(self, rule_data):
            """Install a downloaded rule set as a new profile"""
            name = rule_data.get('name', 'Community Rule')
            rules = rule_data.get('rules', [])
            
            # Create unique name
            base_name = name
            counter = 1
            while os.path.exists(os.path.join(profiles_dir, f"{base_name}.json")):
                base_name = f"{name} ({counter})"
                counter += 1
            
            path = os.path.join(profiles_dir, f"{base_name}.json")
            with open(path, 'w') as f:
                json.dump(rules, f)
            
            return {"success": True, "profile": base_name}

        def get_ai_config(self):
            if os.path.exists(ai_config_file):
                try:
                    with open(ai_config_file, 'r') as f:
                        return json.load(f)
                except:
                    return {}
            return {}

        def save_ai_config(self, config):
            with open(ai_config_file, 'w') as f:
                json.dump(config, f)
            return True

        def _extract_content(self, file_path):
            """
            Extracts text content from various file types.
            Returns text string or None if extraction failed/unsupported.
            """
            try:
                # Check if file is accessible/valid size
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    return None
                    
                ext = os.path.splitext(file_path)[1].lower()
                text = ""
                
                # 1. Text files
                if ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.c', '.cpp', '.h', '.java']:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                
                # 2. PDF
                elif ext == '.pdf':
                    with open(file_path, 'rb') as f:
                        try:
                            reader = PyPDF2.PdfReader(f)
                            # Read max 5 pages to stay within limits roughly
                            for i in range(min(len(reader.pages), 5)):
                                page_text = reader.pages[i].extract_text()
                                if page_text:
                                    text += page_text + "\n"
                        except Exception as e:
                            print(f"PDF Error {file_path}: {e}")
                            return None
                
                # 3. DOCX
                elif ext == '.docx':
                    try:
                        doc = docx.Document(file_path)
                        text = "\n".join([p.text for p in doc.paragraphs])
                    except Exception as e:
                        print(f"DOCX Error {file_path}: {e}")
                        return None
                
                # 4. Images (OCR)
                elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                    try:
                        text = pytesseract.image_to_string(Image.open(file_path))
                    except:
                        return None
                
                if text:
                    # Sanitize: Remove control characters that might break JSON later
                    # Keep newlines, tabs, but remove others
                    text = "".join(ch for ch in text if ch == '\n' or ch == '\t' or ch >= ' ')
                    return text
                    
                return None
            except Exception as e:
                # Silently fail for individual files (e.g. cloud placeholders, locked files)
                # print(f"Extraction error for {file_path}: {e}")
                return None

        def run_ai_scan(self, config):
            api_key = config.get("api_key")
            mode = config.get("mode", "name_only") # name_only or content
            instructions = config.get("instructions", "")
            prioritize_rules = config.get("prioritize_rules", True)
            respect_ignore = config.get("respect_ignore", True)
            
            # Pagination / Limits
            limit = int(config.get("batch_size", 15))
            offset = int(config.get("offset", 0))
            
            # OpenAI Config
            base_url = config.get("base_url", "https://api.sambanova.ai/v1")
            model_name = config.get("model_name", "Meta-Llama-3.1-8B-Instruct")
            
            # Allow empty key for local/custom endpoints (use dummy)
            if not api_key:
                if any(x in base_url for x in ["localhost", "127.0.0.1", "0.0.0.0", "lmstudio", "ollama"]):
                    api_key = "dummy-key"
                else:
                    return {"error": "API Key is required"}
            
            target_path = self.get_target_path()
            files_to_analyze = []
            
            # 1. Scan files
            try:
                all_files = [f for f in os.listdir(target_path) 
                             if os.path.isfile(os.path.join(target_path, f)) 
                             and not f.startswith('.')]
                all_files.sort() # Ensure deterministic order for pagination
                
                # Check ignore/include lists
                ignore_patterns = self.get_ignore_list()
                include_patterns = self.get_include_list()
                filter_mode = self.get_filter_mode()

                valid_files = []
                for f in all_files:
                    # Check filter logic
                    should_skip = False
                    if respect_ignore:
                        if filter_mode == "exclude":
                            for pattern in ignore_patterns:
                                if fnmatch.fnmatch(f, pattern):
                                    should_skip = True
                                    break
                        else: # include
                            matches_include = False
                            for pattern in include_patterns:
                                if fnmatch.fnmatch(f, pattern):
                                    matches_include = True
                                    break
                            if not matches_include:
                                should_skip = True

                    if not should_skip:
                        valid_files.append(f)
                
                total_valid = len(valid_files)

                if not valid_files:
                     if not all_files:
                        return {"error": "Target folder is empty."}
                     else:
                        return {"error": "All files filtered out by Ignore/Include list."}

                # Apply Pagination
                files_to_scan = valid_files[offset : offset + limit]
                
                if not files_to_scan:
                    return {
                        "success": True, 
                        "results": [],
                        "total_valid": total_valid,
                        "is_complete": True
                    }
                
                for f in files_to_scan:
                    file_info = {"name": f}
                    
                    if mode == "content":
                        full_path = os.path.join(target_path, f)
                        content = self._extract_content(full_path)
                        
                        if content:
                            # Check limits: 10,000 chars OR 400 lines
                            if len(content) > 10000 or content.count('\n') > 400:
                                pass 
                            else:
                                try:
                                    # Summarize
                                    parser = PlaintextParser.from_string(content, Tokenizer("english"))
                                    summarizer = LsaSummarizer()
                                    summary = summarizer(parser.document, 5) # Top 5 sentences
                                    summary_text = " ".join([str(s) for s in summary])
                                    file_info["summary"] = summary_text[:400] 
                                except Exception as e:
                                    pass # Skip content if summarization fails
                    
                    files_to_analyze.append(file_info)

            except Exception as e:
                return {"error": f"Scan Error: {str(e)}"}

            # 2. Call OpenAI Compatible API
            try:
                from openai import OpenAI
                
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url
                )

                # Get Rules for context
                rules = self.get_rules()
                
                prompt = f"""
                You are a smart file organizer.
                
                User Instructions: {instructions if instructions else "Sort these files into logical folders based on name and content."}
                
                {f"1. STRICTLY Follow the User's Rules below if they match." if prioritize_rules else "1. IGNORE the User's Rules if they are too generic. Prioritize creating specific subfolders based on the file's unique context."}
                2. Follow the User's Custom Instructions below.
                3. Analyze the **FULL filename** for context (keywords, dates, project names), NOT just the extension.
                4. **OUTPUT FORMAT**: Return a **SINGLE LINE** of valid JSON. **NO NEWLINES**. **NO INDENTATION**.
                
                IMPORTANT PRIORITIES:
                - Group related files (e.g. "Invoice_Jan.pdf", "Invoice_Feb.pdf" -> "Invoices")
                - Create generic folders ONLY if no specific context exists (e.g. "Documents", "Images")
                - If a file is "unknown" or "trash", suggest a "Misc" or "Review" folder.
                
                Return ONLY a JSON object with this structure:
                {{"suggestions":[{{"file":"filename.ext","folder":"SuggestedFolder","reason":"Short reason (max 5 words)"}}]}}
                
                User's Rules:
                {json.dumps(rules) if prioritize_rules else "[]"}

                Files to Analyze:
                {json.dumps(files_to_analyze)}
                """

                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful file organization assistant that outputs JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    stream=False
                )
                
                content = response.choices[0].message.content
                
                # Extract JSON if wrapped in markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                    
                # Handle strict=False for potential control characters
                try:
                    parsed = json.loads(content, strict=False)
                except json.JSONDecodeError:
                    # Fallback: Aggressive Repair
                    try:
                        # 1. Clean up whitespace/markdown
                        content = content.strip()
                        if content.startswith("```json"): content = content[7:]
                        if content.startswith("```"): content = content[3:]
                        if content.endswith("```"): content = content[:-3]
                        content = content.strip()
                        
                        # 2. Try to find the array start
                        start_idx = content.find('[')
                        if start_idx == -1: raise Exception("No array found")
                        
                        # 3. Find the last closing brace '}' to cut off incomplete objects
                        last_brace_idx = content.rfind('}')
                        if last_brace_idx == -1: raise Exception("No objects found")
                        
                        # Keep only up to the last valid object
                        valid_content = content[start_idx:last_brace_idx+1]
                        
                        # Close the array and object
                        fixed_json = f'{{"suggestions": {valid_content}]}}'
                        
                        parsed = json.loads(fixed_json, strict=False)
                    except:
                         # 3. Nuclear Option: Regex extract specific fields
                         try:
                             suggestions = []
                             matches = re.findall(r'"file"\s*:\s*"(.*?)",\s*"folder"\s*:\s*"(.*?)",\s*"reason"\s*:\s*"(.*?)"', content)
                             for m in matches:
                                 suggestions.append({
                                     "file": m[0],
                                     "folder": m[1],
                                     "reason": m[2]
                                 })
                             
                             if not suggestions: raise Exception("Regex failed")
                             parsed = {"suggestions": suggestions}
                         except:
                             return {"error": f"AI Response Invalid/Truncated. Raw: {content[:100]}..."}

                self.ai_results = parsed.get("suggestions", [])
                
                if not self.ai_results:
                        return {"error": "AI analyzed the files but returned no suggestions. Try changing your instructions."}
                        
                return {
                    "success": True, 
                    "results": self.ai_results,
                    "processed": len(files_to_scan),
                    "total_valid": total_valid,
                    "is_complete": (offset + len(files_to_scan)) >= total_valid
                }

            except Exception as e:
                return {"error": f"API Error: {str(e)}"}

        def apply_ai_changes(self, approved_files):
            target_path = self.get_target_path()
            moved_count = 0
            errors = 0
            
            undo_log = []
            
            for item in approved_files:
                filename = item['file']
                folder = item['folder']
                
                src = os.path.join(target_path, filename)
                
                # Check if folder is absolute or relative
                if os.path.isabs(folder):
                    dst_dir = folder
                else:
                    dst_dir = os.path.join(target_path, folder)
                    
                dst = os.path.join(dst_dir, filename)
                
                if os.path.exists(src):
                    try:
                        if not os.path.exists(dst_dir):
                            os.makedirs(dst_dir)
                            
                        # Handle dupes
                        if os.path.exists(dst):
                            base, ext = os.path.splitext(filename)
                            counter = 1
                            while os.path.exists(os.path.join(dst_dir, f"{base}_{counter}{ext}")):
                                counter += 1
                            dst = os.path.join(dst_dir, f"{base}_{counter}{ext}")
                            
                        shutil.move(src, dst)
                        moved_count += 1
                        undo_log.append({"original_path": src, "new_path": dst})
                        
                        webview.windows[0].evaluate_js(f'window.logAction({json.dumps({"file": filename, "category": folder, "status": "Moved (AI)"})})')
                    except Exception as e:
                        errors += 1
                        print(e)
            
            # Save history
            if moved_count > 0:
                session_data = {
                    "id": int(time.time()),
                    "date": time.strftime("%Y-%m-%d %H:%M:%S") + " (AI)",
                    "path": target_path,
                    "moves": undo_log
                }
                
                history = []
                if os.path.exists(history_file):
                    try:
                        with open(history_file, 'r') as f:
                            history = json.load(f)
                    except:
                        pass
                
                history.append(session_data)
                with open(history_file, 'w') as f:
                    json.dump(history, f)

            return {"moved": moved_count, "errors": errors}

        def get_rules(self):
            # Load active profile rules
            active_profile = self.get_active_profile()
            profile_path = os.path.join(profiles_dir, f"{active_profile}.json")
            
            if os.path.exists(profile_path):
                try:
                    with open(profile_path, 'r') as f:
                        return json.load(f)
                except:
                    pass
            
            # Default rules if none exist or profile broken
            defaults = [
                {"name": "Images", "extensions": ["jpg", "jpeg", "png", "gif", "webp"], "folder": "Images"},
                {"name": "Documents", "extensions": ["pdf", "doc", "docx", "txt"], "folder": "Documents"},
                {"name": "Archives", "extensions": ["zip", "rar", "7z", "tar", "gz"], "folder": "Archives"},
                {"name": "Video", "extensions": ["mp4", "mov", "mkv", "webm"], "folder": "Video"},
                {"name": "Audio", "extensions": ["mp3", "wav", "flac"], "folder": "Audio"}
            ]
            
            # If default profile doesn't exist, create it with defaults
            if active_profile == "Default" and not os.path.exists(profile_path):
                with open(profile_path, 'w') as f:
                    json.dump(defaults, f)
                    
            return defaults

        def save_rules(self, rules):
            active_profile = self.get_active_profile()
            profile_path = os.path.join(profiles_dir, f"{active_profile}.json")
            
            with open(profile_path, 'w') as f:
                json.dump(rules, f)
            return True
            
        def get_target_path(self):
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r') as f:
                        settings = json.load(f)
                        path = settings.get("target_path")
                        if path and os.path.exists(path):
                            return path
                except:
                    pass
            return os.path.join(os.path.expanduser("~"), "Downloads")

        def set_target_path(self, path):
            settings = {}
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r') as f:
                        settings = json.load(f)
                except:
                    pass
            
            settings["target_path"] = path
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
        
        def select_folder(self):
            folder = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            if folder and len(folder) > 0:
                self.set_target_path(folder[0])
                return folder[0]
            return None

        def _is_system_folder(self, path):
            path = os.path.abspath(path)
            # Basic checks
            if os.name == 'nt': # Windows
                sys_dirs = [
                    os.environ.get('SystemRoot', 'C:\\Windows'),
                    os.environ.get('ProgramFiles', 'C:\\Program Files'),
                    os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
                ]
                # Also prevent root of C drive
                if path.lower().rstrip('\\') == 'c:': return True
            else: # Mac/Linux
                sys_dirs = ['/System', '/bin', '/sbin', '/usr', '/var', '/etc']
                if path == '/': return True

            for sys_dir in sys_dirs:
                if sys_dir and path.lower().startswith(sys_dir.lower()):
                    return True
            return False

        def select_destination_folder(self):
            """
            Select a destination folder for rules.
            """
            folder = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            if folder and len(folder) > 0:
                path = folder[0]
                # Validate path (prevent system folders)
                if self._is_system_folder(path):
                    return {"error": "System folders are protected. Please choose a user folder."}
                return {"path": path}
            return None

        def get_ignore_list(self):
            if os.path.exists(ignore_file):
                try:
                    with open(ignore_file, 'r') as f:
                        return json.load(f)
                except:
                    return []
            return []

        def save_ignore_list(self, patterns):
            with open(ignore_file, 'w') as f:
                json.dump(patterns, f)
            return True

        def get_include_list(self):
            if os.path.exists(include_file):
                try:
                    with open(include_file, 'r') as f:
                        return json.load(f)
                except:
                    return []
            return []

        def save_include_list(self, patterns):
            with open(include_file, 'w') as f:
                json.dump(patterns, f)
            return True
        
        def get_filter_mode(self):
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r') as f:
                        settings = json.load(f)
                        return settings.get("filter_mode", "exclude")
                except:
                    pass
            return "exclude"

        def set_filter_mode(self, mode):
            settings = {}
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r') as f:
                        settings = json.load(f)
                except:
                    pass
            
            settings["filter_mode"] = mode
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
            return True

        def get_history(self):
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r') as f:
                        history = json.load(f)
                        # Return summary only
                        summary = []
                        for session in history:
                            summary.append({
                                "id": session["id"],
                                "date": session["date"],
                                "path": session["path"],
                                "count": len(session["moves"])
                            })
                        # Sort by date desc
                        return sorted(summary, key=lambda x: x["id"], reverse=True)
                except:
                    return []
            return []

        def restore_session(self, session_id):
            if not os.path.exists(history_file):
                return
            
            def run_restore():
                try:
                    with open(history_file, 'r') as f:
                        history = json.load(f)
                    
                    # Find session
                    session = next((s for s in history if s["id"] == session_id), None)
                    if not session:
                        raise Exception("Session not found")
                        
                    moves = session["moves"]
                    total = len(moves)
                    restored = 0
                    
                    # Reverse order
                    for i, entry in enumerate(reversed(moves)):
                        src = entry['new_path']
                        dst = entry['original_path']
                        
                        if os.path.exists(src):
                            try:
                                shutil.move(src, dst)
                                restored += 1
                                
                                # Check if folder is empty and remove it
                                folder = os.path.dirname(src)
                                if not os.listdir(folder):
                                    os.rmdir(folder)
                                
                                webview.windows[0].evaluate_js(f'window.logAction({json.dumps({"file": os.path.basename(dst), "category": "Restored", "status": "Undo"})})')
                            except Exception as e:
                                print(f"Error restoring {src}: {e}")
                        
                        progress = ((i + 1) / total) * 100
                        webview.windows[0].evaluate_js(f'window.updateProgress({progress})')
                        time.sleep(0.01)

                    # Remove session from history and save
                    new_history = [s for s in history if s["id"] != session_id]
                    with open(history_file, 'w') as f:
                        json.dump(new_history, f)
                        
                    webview.windows[0].evaluate_js(f'window.undoComplete({restored})')
                    
                except Exception as e:
                    webview.windows[0].evaluate_js(f'window.cleaningError("Restore failed: {str(e)}")')

            threading.Thread(target=run_restore).start()

        def _get_display_path(self, full_path):
            home = os.path.expanduser("~")
            path = full_path
            
            if full_path.startswith(home):
                path = full_path.replace(home, "~", 1)
                
            parts = path.split(os.sep)
            # Filter empty parts
            parts = [p for p in parts if p]
            
            # Handle root or home
            if len(parts) == 0:
                return os.sep
            if len(parts) == 1 and parts[0] == "~":
                return "~/"
            
            # If it starts with ~, try to preserve it
            if parts[0] == "~":
                # If short enough (e.g. ~/Downloads/Sub), show full
                if len(parts) <= 3:
                    return os.path.join(*parts)
                # If long, show ~/ ... / LastFolder
                return os.path.join("~", "...", parts[-1])
                
            # If absolute path (no ~), show last 2 components with ...
            if len(parts) > 2:
                return "..." + os.sep + os.path.join(*parts[-2:])
            
            return path

        def scan_downloads(self):
            downloads_path = self.get_target_path()
            display_path = self._get_display_path(downloads_path)
            files = []
            try:
                for f in os.listdir(downloads_path):
                    full_path = os.path.join(downloads_path, f)
                    if os.path.isfile(full_path) and not f.startswith('.'):
                        files.append(f)
            except Exception as e:
                return {"error": str(e)}
            
            return {"count": len(files), "path": downloads_path, "display_path": display_path}

        def organize_files(self):
            self.stop_cleaning = False
            downloads_path = self.get_target_path()
            
            # Load rules
            rules = self.get_rules()

            def run_organizer():
                moved_count = 0
                errors = 0
                undo_log = []
                
                # Load filter mode and patterns
                filter_mode = self.get_filter_mode()
                ignore_patterns = self.get_ignore_list()
                include_patterns = self.get_include_list()
                
                try:
                    files = [f for f in os.listdir(downloads_path) 
                             if os.path.isfile(os.path.join(downloads_path, f)) 
                             and not f.startswith('.')]
                    
                    total = len(files)
                    
                    for i, filename in enumerate(files):
                        if self.stop_cleaning:
                            webview.windows[0].evaluate_js('window.cleaningStopped()')
                            return

                        # Check filter logic
                        should_skip = False
                        
                        if filter_mode == "exclude":
                            # Exclude if matches ignore pattern
                            for pattern in ignore_patterns:
                                if fnmatch.fnmatch(filename, pattern):
                                    should_skip = True
                                    break
                        else: # include mode
                            # Skip UNLESS it matches include pattern
                            matches_include = False
                            for pattern in include_patterns:
                                if fnmatch.fnmatch(filename, pattern):
                                    matches_include = True
                                    break
                            if not matches_include:
                                should_skip = True
                        
                        if should_skip:
                            progress = ((i + 1) / total) * 100
                            webview.windows[0].evaluate_js(f'window.updateProgress({progress})')
                            continue

                        file_path = os.path.join(downloads_path, filename)
                        _, ext = os.path.splitext(filename)
                        ext = ext.lower().lstrip('.') # 'pdf' not '.pdf'
                        
                        target_folder = None
                        
                        # Match against rules
                        for rule in rules:
                            # Check extensions (flexible input handling)
                            rule_exts = [e.lower().lstrip('.') for e in rule.get('extensions', [])]
                            
                            if ext in rule_exts:
                                target_folder = rule.get('folder', 'Misc')
                                
                                # Handle dynamic pattern "($)" extraction
                                pattern = rule.get('filename_pattern', '')
                                if pattern and '($)' in pattern:
                                    # Convert "date($)file" to regex "date(.*)file"
                                    parts = pattern.split('($)')
                                    safe_parts = [re.escape(p) for p in parts]
                                    # Use (.*) to capture
                                    regex_pattern = '(.*)'.join(safe_parts)
                                    
                                    extracted = None
                                    
                                    # 1. Try match against base filename first (avoids capturing extension)
                                    base_name, _ = os.path.splitext(filename)
                                    match = re.search(regex_pattern, base_name)
                                    if match:
                                        groups = match.groups()
                                        if groups:
                                            extracted = " ".join([g.strip() for g in groups if g])
                                            
                                    # 2. If no match, try full filename (in case pattern includes extension)
                                    if not extracted:
                                        match = re.search(regex_pattern, filename)
                                        if match:
                                            groups = match.groups()
                                            if groups:
                                                extracted = " ".join([g.strip() for g in groups if g])

                                    if extracted:
                                        # Append extracted value as subfolder
                                        target_folder = os.path.join(target_folder, extracted)
                                
                                break # Stop at first matching rule
                        
                        if not target_folder:
                             # No rule matched, skip or move to Misc? 
                             # Let's skip for now to be safe, or we can have a "Misc" rule
                             progress = ((i + 1) / total) * 100
                             webview.windows[0].evaluate_js(f'window.updateProgress({progress})')
                             continue

                        # Determine target directory (Absolute or Relative)
                        if os.path.isabs(target_folder):
                            target_dir = target_folder
                        else:
                            target_dir = os.path.join(downloads_path, target_folder)
                            
                        if not os.path.exists(target_dir):
                            os.makedirs(target_dir)
                            
                        target_path = os.path.join(target_dir, filename)
                        
                        # Handle duplicates
                        if os.path.exists(target_path):
                            base, extension = os.path.splitext(filename)
                            counter = 1
                            while os.path.exists(os.path.join(target_dir, f"{base}_{counter}{extension}")):
                                counter += 1
                            target_path = os.path.join(target_dir, f"{base}_{counter}{extension}")
                            filename = f"{base}_{counter}{extension}"

                        try:
                            shutil.move(file_path, target_path)
                            moved_count += 1
                            
                            undo_log.append({
                                "original_path": file_path,
                                "new_path": target_path
                            })
                            
                            log_entry = {
                                "file": filename,
                                "category": target_folder,
                                "status": "Moved"
                            }
                            webview.windows[0].evaluate_js(f'window.logAction({json.dumps(log_entry)})')
                            
                        except Exception as e:
                            errors += 1
                            log_entry = {
                                "file": filename,
                                "category": target_folder,
                                "status": "Error",
                                "details": str(e)
                            }
                            webview.windows[0].evaluate_js(f'window.logAction({json.dumps(log_entry)})')
                        
                        # Update progress
                        progress = ((i + 1) / total) * 100
                        webview.windows[0].evaluate_js(f'window.updateProgress({progress})')
                        
                        # Add a tiny delay to make it look cool/visualize the process
                        time.sleep(0.05)

                    # Save history
                    if moved_count > 0:
                        session_data = {
                            "id": int(time.time()),
                            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "path": downloads_path,
                            "moves": undo_log
                        }
                        
                        history = []
                        if os.path.exists(history_file):
                            try:
                                with open(history_file, 'r') as f:
                                    history = json.load(f)
                            except:
                                pass
                        
                        history.append(session_data)
                        
                        with open(history_file, 'w') as f:
                            json.dump(history, f)
                        
                    webview.windows[0].evaluate_js(f'window.cleaningComplete({moved_count}, {errors})')

                except Exception as e:
                    webview.windows[0].evaluate_js(f'window.cleaningError("{str(e)}")')

            threading.Thread(target=run_organizer).start()

    api = Api()
    webview.create_window('System Cleaner', url=index_path, js_api=api, width=800, height=600)
    webview.start(debug=False)

if __name__ == '__main__':
    create_app()
