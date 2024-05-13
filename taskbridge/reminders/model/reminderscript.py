"""
AppleScripts for Apple Reminders.
"""

#: Get the list of local reminder lists.
get_reminder_lists_script = '''tell application "Reminders"
    set output to ""
    set r_lists to get every list
    repeat with r_list in r_lists
        set list_id to id of r_list
        set list_name to name of r_list
        if output is "" then
            set token to ""
        else
            set token to "|"
        end if
        set output to output & token & list_id & ":" & list_name
    end repeat
    return output
end tell'''

#: Create a new reminder list.
create_reminder_list_script = '''on run argv
set list_name to item 1 of argv
tell application "Reminders"
    set theList to make new list
    set name of theList to list_name
    return id of theList
end tell
end run'''

#: Get the list of reminders in a reminder list.
get_reminders_in_list_script = '''on run argv
set list_name to item 1 of argv
tell application "Reminders"
    set upcomingReminders to every reminder of list list_name whose completed is false
    set fileContent to ""
    repeat with currentRem in upcomingReminders
        set rId to id of currentRem
        set rName to name of currentRem
        set rCreationDate to creation date of currentRem
        set rBody to body of currentRem
        set rCompleted to completed of currentRem
        set rDueDate to due date of currentRem
        set rAllDay to allday due date of currentRem
        set rRemindMeDate to remind me date of currentRem
        set rModificationDate to modification date of currentRem
        set rCompletionDate to completion date of currentRem
        set csvLine to rId & "|" & rName & "|" & rCreationDate & "|" & rCompleted & "|" & rDueDate & "|" & rAllDay & "|"
        set csvLine to csvLine & rRemindMeDate & "|" & rModificationDate & "|" & rCompletionDate & "|" & rBody & linefeed
        set fileContent to fileContent & csvLine
    end repeat
end tell
set accessRef to (open for access file ((path to temporary items folder as text) & list_name & ".psv") with write permission)
    try
        set eof accessRef to 0
        write fileContent to accessRef
        close access accessRef
        set save_location to POSIX path of (path to temporary items folder) as text
        return save_location
    on error errMsg
        close access accessRef
        log errMsg
    end try
end run'''

#: Add a new reminder to the given list in the default account.
add_reminder_script = '''on run argv
set {r_id, r_name, r_body, r_completed, r_completed_date} to {item 1, item 2, item 3, item 4, item 5} of argv
set {r_due_date, r_allday_due, r_remind_date, r_list} to {item 6, item 7, item 8, item 9} of argv
tell application "Reminders"
    set mylist to list r_list
    tell mylist
    if r_id is equal to "" then
      set theReminder to make new reminder at end of mylist
    else
      set theReminder to reminder id r_id
    end if
    set name of theReminder to r_name
    if r_body is not equal to "" then
      set body of theReminder to r_body
    end if
    set completed of theReminder to r_completed
    if r_completed_date is not equal to "" then
      set completion date of theReminder to my stringToDate(r_completed_date)
    end if
    if r_remind_date is not equal to "" then
      set remind me date of theReminder to my stringToDate(r_remind_date)
    end if
    if r_due_date is not equal to "" then
      if r_allday_due is true then
        set allday due date of theReminder to my stringToDate(r_due_date)
      else
        set due date of theReminder to my stringToDate(r_due_date)
      end if
    end if
    end tell
end tell
    return id of theReminder
end run

on stringToDate(theDateStr)
    set theDate to date theDateStr
    return theDate
end stringToDate
'''

#: Delete the reminder with the given UUID.
delete_reminder_script = '''on run argv
set r_id to item 1 of argv
tell application "Reminders"
    delete reminder id r_id
end tell
end run'''

#: Delete the list with the given name in the default account.
delete_list_script = '''on run argv
set r_list to item 1 of argv
tell application "Reminders"
    delete list r_list
end tell
end run'''

#: Get the number of completed reminders.
count_completed_script = '''on run argv
tell application "Reminders"
    set completedReminders to every reminder whose completed is true
    set output to count of completedReminders
    return output
end tell
end run'''

#: Delete completed reminders.
delete_completed_script = '''on run argv
tell application "Reminders"
    delete every reminder whose completed is true
end tell
end run'''

#: Check if the Reminders app is running
is_reminders_running_script = '''tell application "System Events"
if (get name of every application process) contains "Reminders" then
    return true
else
    return false
end if
end tell'''

#: Quit the Reminders app
quit_reminders_script = '''tell application "Reminders" to if it is running then quit'''
