"""
AppleScript for Apple Notes.
"""

#:  Get the list of notes from a folder and export as a staged file.
get_notes_script = """on run argv
set folder_name to item 1 of argv
tell application "Finder"
    set save_location to (POSIX path of (path to temporary items folder) as text) & "taskbridge/notesync/" & folder_name
    do shell script "mkdir -p " & quoted form of save_location
end tell
tell application "Notes"
    set myFolder to first folder whose name = folder_name
    set myNotes to notes of myFolder
    repeat with theNote in myNotes
        set nId to id of theNote
        set nName to name of theNote
        set nBody to body of theNote
        set nCreation to creation date of theNote
        set nModified to modification date of theNote
        set attachmentList to "~~START_ATTACHMENTS~~\n"
        repeat with theAttachment in attachments of theNote
          set attachmentList to attachmentList & name of theAttachment & "~~" & url of theAttachment & "\n"
        end repeat
        set attachmentList to attachmentList & "~~END_ATTACHMENTS~~"
        set stagedContent to nId & "~~" & nName & "~~" & nCreation & "~~" & nModified
        set stagedContent to stagedContent & "\n" & attachmentList & "\n" & nBody
        tell application "Finder"
            set aPath to "taskbridge:notesync:" & folder_name & ":" & nName & ".staged"
            set accessRef to (open for access file ((path to temporary items folder as text) & aPath) with write permission)
            try
                set eof accessRef to 0
                write stagedContent to accessRef as «class utf8»
                close access accessRef
            on error errMsg
                close access accessRef
                log errMsg
            end try
        end tell
    end repeat
end tell
return save_location
end run"""

#: Create a new local note.
create_note_script = r"""on run argv
set {note_folder, note_name, export_file} to {item 1, item 2, item 3} of argv
set note_folder to note_folder

tell application "Finder"
  set input_file to my POSIX file export_file
  set input_lines to read input_file as «class utf8» using delimiter linefeed
end tell

tell application "Notes"
  tell folder note_folder
    set theNote to make new note
      tell theNote
        set note_body to "<h1>" & note_name & "</h1>"
        repeat with note_line in input_lines
            if note_line contains "<img" then
              -- Image Attachment
              set sed_extract to "echo '" & note_line & "' | sed -n 's/.*src=\"\\([^\"]*\\)\".*/\\1/p'"
              set image_url to do shell script sed_extract
              set theFile to (image_url) as POSIX file
              make new attachment at end of attachments with data theFile
              set note_body to note_body & "<div><img style=\"max-width: 100%; max-height: 100%;\" src=\"" & image_url & "\"/>
              <div><br></div>"
            else
              -- Normal Line
              set note_body to note_body & note_line
            end if
        end repeat
        set body to note_body
      end tell
  end tell
end tell
return modification date of theNote
end run"""

#: Update a local note.
update_note_script = r"""on run argv
set {note_folder, note_name, export_file} to {item 1, item 2, item 3} of argv
set note_folder to note_folder

tell application "Finder"
  set input_file to my POSIX file export_file
  set input_lines to read input_file as «class utf8» using delimiter linefeed
end tell

tell application "Notes"
  tell folder note_folder
    set theNote to note note_name
      tell theNote
        set note_body to "<h1>" & note_name & "</h1>"
        repeat with note_line in input_lines
            if note_line contains "<img" then
              -- Image Attachment
              set sed_extract to "echo '" & note_line & "' | sed -n 's/.*src=\"\\([^\"]*\\)\".*/\\1/p'"
              set image_url to do shell script sed_extract
              set theFile to (image_url) as POSIX file
              make new attachment at end of attachments with data theFile
              set note_body to note_body & "<div><img style=\"max-width: 100%; max-height: 100%;\" src=\"" & image_url & "\"/>
              <div><br></div>"
            else
              -- Normal Line
              set note_body to note_body & note_line
            end if
        end repeat
        set body to note_body
      end tell
  end tell
end tell
return modification date of theNote
end run"""

#: Delete a local note.
delete_note_script = """on run argv
set {note_folder, note_name} to {item 1, item 2} of argv
tell application "Notes"
    tell folder note_folder
        set theNote to note note_name
        delete theNote
    end tell
end tell
end run"""

#: Load the list of local folders from the default account.
load_folders_script = """tell application "Notes"
    set output to ""
    set n_folders to get every folder
    repeat with n_folder in n_folders
        set folder_id to id of n_folder
        set folder_name to name of n_folder
        if output is "" then
            set token to ""
        else
            set token to "|"
        end if
        set output to output & token & folder_id & "~~" & folder_name
    end repeat
    return output
end tell
"""

#: Create a new local folder in the default account.
create_folder_script = """on run argv
set folder_name to item 1 of argv
tell application "Notes"
    set theFolder to make new folder
    set name of theFolder to folder_name
    return id of theFolder
end tell
end run
"""

#: Delete a local folder.
delete_folder_script = """on run argv
set note_folder to item 1 of argv
tell application "Notes"
    tell folder note_folder
        delete it
    end tell
end tell
end run"""

#: Check if the Notes app is running
is_notes_running_script = '''tell application "System Events"
if (get name of every application process) contains "Notes" then
    return true
else
    return false
end if
end tell'''

#: Quit the Notes app
quit_notes_script = '''tell application "Notes" to if it is running then quit'''
