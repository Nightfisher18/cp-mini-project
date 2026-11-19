import pandas as pd 
from datetime import datetime, timezone, timedelta

# FIX: Force IST (UTC+5:30) so Render's UTC server displays correct local time
IST = timezone(timedelta(hours=5, minutes=30))


# Creating a Queue class for the entire queuing system
class PatientQueue:
    #Initializing an empty Dataframe to be filled with patients
    def __init__(self):
        self.df = pd.DataFrame(columns=['Token Number','Name','Age','Ailment','Time of entry','Gender'])
        #mannual token counter
        self.token_counter = 1 
        # ADDED: Track currently serving token and completed/cancelled tokens for status & stats
        self.current_serving = None
        self.served_tokens = []
        self.cancelled_tokens = []

    #Function to add a patient at the end of the list 
    def add(self, name, age, ailment, gender):
        #time of arrival
        # FIX: Added %Y-%m-%d date format and IST so duration math doesn't default to year 1900 or UTC
        time = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")
        token_assigned = self.token_counter
        #details of the new patient as a new line for the dataframe 
        new_line = pd.DataFrame([{
            'Token Number': token_assigned,
            'Name': name,
            'Age': age,
            'Ailment':ailment,
            'Time of entry': time,
            'Gender': gender
        }])
        #concatinating the new line with the exisitng data in the dataframe
        # FIX: Avoid Pandas FutureWarning when concatenating into an empty DataFrame
        if self.df.empty:
            self.df = new_line
        else:
            self.df = pd.concat([self.df, new_line], ignore_index=True)
        self.token_counter += 1 
        # ADDED: Return dict so Flask API can send JSON response later
        return {
            'token_number': token_assigned,
            'name': name,
            'time_of_entry': time,
            'position_in_queue': len(self.df)
        }

    def remove(self):
        #checking if the dataframe is not empty
        if self.df.empty:
            print("The queue is empty")
            # ADDED: Mark last serving patient as served when queue empties
            if self.current_serving is not None:
                self.served_tokens.append(self.current_serving['token_number'])
                self.current_serving = None
            return None
        else:
            #taking info to print out hte exit summary( even the time and all)
            entry_time_str = self.df.loc[0, 'Time of entry']
            patient_name = self.df.loc[0, 'Name']
            # FIX: Cast to standard Python int so Flask jsonify() won't fail on numpy.int64
            patient_token = int(self.df.loc[0, 'Token Number'])

            #Dropping the patient itself
            # FIX: Added reset_index(drop=True) to prevent KeyError: 0 on the next remove()
            self.df = self.df.drop(0).reset_index(drop=True)

            #converting string time to datetime object
            # FIX: Parse full date + time with IST timezone to match entry format
            entry_dt = datetime.strptime(entry_time_str, "%Y-%m-%d %I:%M:%S %p").replace(tzinfo=IST)
            exit_dt = datetime.now(IST)
            # FIX: Renamed 'exit' to 'exit_str' to avoid shadowing Python's built-in exit()
            exit_str = exit_dt.strftime("%Y-%m-%d %I:%M:%S %p")
            #finding duration of stay 
            time_delta = exit_dt - entry_dt
            total_time = int(time_delta.total_seconds())
            # FIX: Renamed 'min' to 'mins' to avoid shadowing Python's built-in min()
            mins, secs = divmod(total_time, 60)

            # ADDED: Move previous patient to served history and set this patient as currently serving
            if self.current_serving is not None:
                self.served_tokens.append(self.current_serving['token_number'])
            self.current_serving = {'token_number': patient_token, 'name': patient_name}

            #printing exit summary 
            print("Patient Details:")
            print(f"Name: {patient_name} Token: {patient_token}")
            print(f"Exit time: {exit_str} Duration: {mins} minutes {secs} seconds")

            return {
                'name': patient_name,
                'token_number': patient_token,
                'exit_time': exit_str,
                'duration_minutes': mins,
                'duration_seconds': secs
            }

    #function to actually show the dataframe        
    def show(self):
        if self.df.empty:
            print("Empty Queue")
            return []
        else:
            print(f"Current Patient Queue:\n{self.df.to_string()}")
            return self.df.to_dict(orient='records')

    # --- NEW ESSENTIAL & UNIQUE FUNCTIONS ---

    # Essential: Lets a user check their token status and queue position
    def check_status(self, token_number):
        current_token = self.current_serving['token_number'] if self.current_serving else None
        matches = self.df[self.df['Token Number'] == token_number]

        if not matches.empty:
            position = int(matches.index[0]) + 1
            people_ahead = position - 1
            return {
                'token_number': token_number,
                'status': 'Waiting',
                'position_in_queue': position,
                'people_ahead': people_ahead,
                'currently_serving': current_token
            }
        elif current_token == token_number:
            return {
                'token_number': token_number,
                'status': 'Currently Serving',
                'position_in_queue': 0,
                'currently_serving': current_token
            }
        elif token_number in self.served_tokens:
            return {
                'token_number': token_number,
                'status': 'Served',
                'position_in_queue': None,
                'currently_serving': current_token
            }
        elif token_number in self.cancelled_tokens:
            return {
                'token_number': token_number,
                'status': 'Cancelled',
                'position_in_queue': None,
                'currently_serving': current_token
            }
        else:
            return {
                'token_number': token_number,
                'status': 'Invalid Token',
                'position_in_queue': None,
                'currently_serving': current_token
            }

    # Unique: Priority / Emergency insertion that places a critical patient at the front of the queue
    def add_emergency(self, name, age, ailment, gender):
        time = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")
        token_assigned = self.token_counter
        new_line = pd.DataFrame([{
            'Token Number': token_assigned,
            'Name': name,
            'Age': age,
            'Ailment': f"[EMERGENCY] {ailment}",
            'Time of entry': time,
            'Gender': gender
        }])

        if self.df.empty:
            self.df = new_line
        else:
            # Place new_line BEFORE self.df so emergency patient jumps to index 0
            self.df = pd.concat([new_line, self.df], ignore_index=True)

        self.token_counter += 1
        return {
            'token_number': token_assigned,
            'name': name,
            'priority': 'Emergency',
            'time_of_entry': time,
            'position_in_queue': 1
        }

    # Essential: Allows a patient to cancel their token and leave the queue without disturbing others
    def cancel_token(self, token_number):
        matches = self.df[self.df['Token Number'] == token_number]
        if matches.empty:
            return None

        patient_name = matches.iloc[0]['Name']
        self.df = self.df[self.df['Token Number'] != token_number].reset_index(drop=True)
        self.cancelled_tokens.append(int(token_number))
        return {'token_number': int(token_number), 'name': patient_name, 'status': 'Cancelled'}

    # Essential (Admin Dashboard): Returns live queue metrics
    def queue_stats(self):
        return {
            'currently_serving': self.current_serving,
            'waiting_count': len(self.df),
            'served_count': len(self.served_tokens) + (1 if self.current_serving else 0),
            'cancelled_count': len(self.cancelled_tokens)
        }