---
layout: default
---

# Welcome!

Welcome to TaskBridge, the app that makes it easy to keep your Apple Notes and Reminders synchronised with cloud
services such as [NextCloud](https://nextcloud.com) and CalDAV.

This guide will help you quickly get started with TaskBrdige and make the most out of it! But first...

# Disclaimer

Although every care has been taken when developing TaskBridge, there are two **important** things you should be aware of:

1. TaskBridge is an app in very early development. It has been tested in a limited number of scenarios on a limited number
   of machines. Therefore, your mileage may vary.
2. Unfortunately, the way that Apple Notes and Reminders are built makes them quite difficult to interact with
   programmatically.
   This means that, at any point, Apple may decide to change how Notes and Reminders work, or disable programmatic interation
   entirely. This means that TaskBridge can stop working without any prior notice!

Due to the above:

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Installation

TODO: Do this.

After launching TaskBridge, you will be presented with the main screen:

![TaskBridge main screen](images/10_mainscreen.png)

Before syncing, you should configure your reminder and note sync. Let's do that next!

# Configuring Reminder Sync

Switch to the **Reminders** tab to start configuring your reminder sync. Once there, click **Synchronise Reminders** to enable
reminder sync. This will prompt you to configure your CalDAV login, i.e. how you will connect to the remote reminder
server TaskBridge will sync with. The remote reminder server can be NextCloud (via NextCloud Tasks) or any other CalDAV
server.

![Enable reminder sync](images/100_reminders.png)

Start by choosing your **Server Type**. This is set to **NextCloud** by default. Then, enter your username. For NextCloud, this
is the same as the username you use to log in to NextCloud. For CalDAV, enter your username (this could also be your email
address).

If you set the server type to NextCloud, the **Tasks Path** field will auto-complete as you type your username. You don't
need to change this, most of the time.

![Autocompleting remote reminder login](images/110_reminders_autocomplete.png)

Fill in the rest of the fields.

- **Server Address**: The address of your server. For example, _`https://nextcloud.mydomain.com`_.
- **Password**: The password for your server. For NextCloud, this is the same password you use to log in to NextCloud.

When you've entered all details, click the **Login** button:

![Logging in to the reminder server](images/120_reminders_login.png)

TaskBridge will then retrieve your reminder lists from the Apple Reminders app, as well as your Task calendars from
NextCloud or CalDAV server. These will be displayed below:

![List of reminder containers](images/130_reminder_containers.png)

The **List Name** column shows the reminder list name. TaskBridge will automatically associate local remidner lists with
remote task calendars if they have the same name. Otherwise, this will either contain the local reminder list name, or the
remote task calendar.

> **Note:** On Apple Reminders,
> the _Reminders_ list is your default container for reminders, whilst on various CalDAV servers including NextCloud, the
> _Tasks_ calendar is the default tasks calendar. For this reason, TaskBrdige always associates the local _Reminders_ list
> with the remote _Tasks_ calendar.

The **Location** column shows the location of the reminders list or calendar, with the following icons:

| Icon                                                | Description                                                                                       |
|:----------------------------------------------------|:--------------------------------------------------------------------------------------------------|
| ![Local list icon](images/icon_home.png)            | This is a local reminder list (i.e. on Apple Reminders).                                          |
| ![Remote calendar icon](images/icon_remote.png)     | This is a remote tasks calendar (i.e. on NextCloud or CalDAV).                                    |
| ![Associated containers icon](images/icon_both.png) | A local reminder list and remote tasks calendar have the same name, so they have been associated. |

Check the reminder lists you would like to sync. Any missing lists will be created. For example, if you have a local reminder
list which doesn't have an associated NextCloud/CalDAV calendar, the calendar will be created before reminders/tasks are
synced.
Similarly, deletions are also synchronised; for example, if you delete the tasks calendar _Work_, and you've chosen for it to
be
synchronised, the local reminder list _Work_ will also be deleted.

![Selecting reminder lists to sync](images/140_reminders_check.png)

Once you're done making changes, click **Save** to commit these changes. TaskBridge will remember these settings and keep
using them until you change them. You can also click **Cancel** to discard all changes. This will refresh the reminder lists
and all other reminder settings to the state prior to your most recent changes.

# Configuring Note Sync

Switch to the **Notes** tab to start configuring your note sync. Once there, click **Synchronise Notes** to enable note
sync. This will prompt you to select your remote Notes folder.

![Notes view](images/200_notes.png)

Your remote notes folder refers to where, on your Mac, the files for your remote notes are stored. TaskBridge will export
your notes from Apple Notes as to this folder (as Markdown files). Your NextCloud Desktop app will then take care of
uploading these to NextCloud Notes. For most users, your NextCloud notes folder will be called **Notes**, and you'll find
it in your home folder. For example, if your name is _Bob_, your Notes folder will be in `/Users/bob/Nextcloud/Notes`.

Browse to the location of your NextCloud Notes folder, and click **Open**.

![Selecting local notes folder](images/210_notes_browse.png)

Once you've chosen your Notes folder, TaskBridge will show a list of local and remote notes folders below:

![Selecting local notes folder](images/220_notes_check.png)

From here, you can select which folders to sync. TaskBridge will automatically associate local and remote note folders
if they have the same name. Otherwise, this will either contain the local folder name, or the remote folder name.

The **Location** column shows the location of the note folder, with the following icons:

| Icon                                                | Description                                                                                    |
|:----------------------------------------------------|:-----------------------------------------------------------------------------------------------|
| ![Local list icon](images/icon_home.png)            | This is a local notes folder (i.e. on Apple Notes).                                            |
| ![Remote calendar icon](images/icon_remote.png)     | This is a remote notes folder (i.e. on NextCloud).                                             |
| ![Associated containers icon](images/icon_both.png) | A local notes folder and remote notes folder have the same name, so they have been associated. |

For each folder, you can then choose how to sync.

| Icon                                                 | Description                                                                              |
|:-----------------------------------------------------|:-----------------------------------------------------------------------------------------|
| ![Upload local icon](images/icon_local_up.png)       | Notes in this folder will be uploaded to NextCloud. No downloads from NextCloud.         |
| ![Download remote icon](images/icon_remote_down.png) | Notes in this folder will be downloaded from NextCloud. No uploads to NextCloud.         |
| ![Bidirectional icon](images/icon_bidirectional.png) | Notes in this folder will be synchronised. Both uploads and downloads to/from NextCloud. |

Missing folders will be created. For example, if you choose to synchronise a folder which is not on NextCloud, the folder will
be created on NextCloud before notes are synchronised.

When checking the synchronisation boxes, TaskBridge will automatically correct your choices. For example, the _Archive_
folder below is currently set to synchronise from the local note folder to the remote NextCloud folder. I then check the
next checkbox, to also synchronise changes from the remote NextCloud folder to the local notes folder:

![Choosing both sync directions](images/230_notes_double.png)

TaskBridge automatically changes your selection to a bidirectional sync, since synchronising local to remote and remote to
local is the same as bidirectional:

![Corrected sync direction](images/240_notes_double.png)

Similarly, if you've selected a bidrectional sync, but then click any of the other two checkboxes, bidirectional sync will
automatically be disabled.

Once you're done making changes, click **Save** to commit these changes. TaskBridge will remember these settings and keep
using them until you change them. You can also click **Cancel** to discard all changes. This will refresh the note folders
and all other notes settings to the state prior to your most recent changes.

# Syncing!

With your settings set, it's time to sync! Switch to the **Sync** tab, and click **Sync** to start synchronisation.

![Sync progress](images/300_sync_progress.png)

Once synchronisation is complete, you'll get a status message:

![Sync complete](images/310_sync_complete.png)

# Configuring Scheduled Sync

Besides a one-off sync, TaskBridge can also be configured to periodically synchronise your reminders. The following schedules
are currently supported:

- Every 10 to 59 minutes.
- Every 1 to 12 hours.

To set up scheduled sync, simply switch to the **Sync** tab and check **Scheduled Sync**:

![Enable scheduled sync](images/400_autosync.png)

Next, choose your schedule, and click **Set Schedule**.

The scheduled sync will use the same settings as you've configured in the **Reminders** and **Notes** tabs. Also, changing
any settings (and saving!) will update the scheduled sync settings.

# The Tray Icon

When you close the TaskBridge window, TaskBridge will keep running in the background. You'll always see the TaskBridge icon
in your Mac's menu bar:

![Tray icon](images/500_menubar.png)

Clicking on the icon allows you to bring up the TaskBridge window, or Quit TaskBridge.

> **Remember**: TaskBridge cannot carry out your scheduled sync when it is not running!

# CLI Usage

A command-line interface is available for TaskBridge. This can be useful if you want to run the sync as a scheduled task via
cron or launchd, or if you want to integrate functionality in your own, non-Python scripts or apps.

### Installing the CLI

The first step is to install the CLI tool. The easiest way to do this is via [pipx](https://github.com/pypa/pipx#readme). If
you don't have pipx installed,
you can easily install it via [HomeBrew](https://brew.sh):

```shell
brew install pipx
pipx ensurepath
```

Once that's done, run the following command to install the TaskBridge CLI. This will install a ```tbcli``` command on your
system.

```shell
pipx install "git+https://github.com/pint-sized/taskbridge.git"
```

### Using the CLI

Usage:

```
TaskBridge CLI [-h] [--sync-notes {0,1}] [--remote-notes-folder REMOTE_NOTES_FOLDER] [--notes-bi-directional NOTES_BI_DIRECTIONAL] [--notes-local-remote NOTES_LOCAL_REMOTE] [--notes-remote-local NOTES_REMOTE_LOCAL] [--sync-reminders {0,1}] [--prune-reminders {0,1}] [--caldav-server CALDAV_SERVER]
                    [--caldav-path CALDAV_PATH] [--caldav-username CALDAV_USERNAME] [--caldav-password] [--reminder-sync REMINDER_SYNC] [--config CONFIG] [--log-dir LOG_DIR] [--log-level {debug,info,critical,warning}]
```

To use the CLI, run ```tbcli```. If you use the TaskBridge GUI, the CLI will pick up the same configuration settings you've set
in the GUI and run the same tasks as would run when using the GUI. If you don't use the GUI, or want to use a different
configuration when running in CLI mode, you can use the ```--config``` option to provide a custom configuration file. For
example:

```shell
tbcli --config=/path/to/my-custom-config.json
```

### Configuration File

The most convenient way to specify configuration options is to create a custom configuration file. The example below shows all
possible configuration options. Note that you do not need to specify all the options, just the ones you need. To understand
what each option does, refer to the [CLI Options](#cli-options) section below.

```yaml
{
  "sync_notes": "1",
  "remote_notes_folder": "/path/to/remote/notes",
  "associations": {
    "bi_directional": [ "Some Folder", "Some Other Folder" ],
    "local_to_remote": [ "Local folder" ],
    "remote_to_local": [ "Remote folder" ]
  },
  "sync_reminders": "1",
  "prune_reminders": "1",
  "caldav_server": "https://myserver.mydomain.com",
  "caldav_path": "/path/to/caldav/calendar",
  "caldav_username": "bob",
  "reminder_sync": [ "Personal", "Reminder List 2" ],
  "log_level": "info"
}
```

### CLI Options

Supported CLI options are described below. Note that using any of these options will override any settings in the
configuration file.

| Option                        | Description                                                      | Example                                            |
|:------------------------------|:-----------------------------------------------------------------|----------------------------------------------------|
| ```--sync-notes```            | Whether to sync notes. "1" enables, "0" disables.                | ```--sync-notes=1```                               |
| ```--remote-notes-folder```   | Location of the remote notes folder.                             | ```--remote-notes-folder="/Users/bob/Notes"```     |
| ```--notes-bidirectional```   | List of notes folders to sync bi-directionally.                  | ```--notes-bidirectional="Notes, Work"```          |
| ```--notes-local-to-remote``` | List of notes folders to sync local --> remote.                  | ```--notes-local-to-remote="Groceries```           |
| ```--notes-remote-to-local``` | List of notes folders to sync local <-- remote.                  | ```--notes-remote-to-local="Travel"```             |
| ```--sync-reminders```        | Whether to sync reminders. "1" enables, "0" disables.            | ```--sync-reminders=1```                           |
| ```--prune-reminders```       | Whether to prune completed reminders. "1" enables, "0" disables. | ```--prune-reminders=1```                          |
| ```--caldav-server```         | Hostname of the CalDAV server for reminder sync.                 | ```--caldav-server="https://mycloud.domain.com"``` |
| ```--caldav-path```           | Path of the remote calendar on the CalDAV server.                | ```--caldav-path="/path/to/caldav/calendar```      |
| ```--caldav-username```       | Username for logging into the CalDAV server.                     | ```--caldav-username="bob"```                      |
| ```--caldav-password```       | If set, this prompts the CLI to ask you for a CalDAV password.   | ```--caldav-password```                            |
| ```--reminder-sync```         | List of reminder lists to synchronise.                           | ```--reminder-sync="Personal, Work"```             |

The following options are specific to the CLI:

| Option            | Description                                                                               | Example                                     |
|:------------------|:------------------------------------------------------------------------------------------|---------------------------------------------|
| ```--config```    | Specify a path to a custom configuration file                                             | ```--config=/Users/bob/tbcli.conf```        |
| ```--log-level``` | Specify the logging level. Supported levels are "debug", "info", "warning" and "critical" | ```--log-level="info"```                    |
| ```--log-dir```   | Specify a custom directory for CLI logs.                                                  | ```--log-dir="/Users/bob/logs/tbcli.log"``` |
| ```-h, --help```  | Display a help message and exit.                                                          |                                             |

# Looking Under the Hood

If you're technical, you can take a peek under the hood to see what TaskBridge is currently doing. From the **Sync** tab,
click the _Show Debug Screen_ icon (shown below) to switch to the Debug screen.

![Show debug screen](images/icon_show_debug.png)

The debug screen shows a log of everything TaskBridge is doing:

![Debug screen](images/900_debugscreen.png)

The amount of information can be overwhelming. You can choose a lower log level from the drop-down list:

![Logging level](images/910_debuglevel.png)

You can also clear existing messages:

![Clear existing logs](images/920_debugdelete.png)

To return to the **Sync** screen, click the _Hide Debug Screen_ icon (shown below):

![Hide debug screen](images/icon_hide_debug.png)

# Limitations

TaskBridge has several known limitations. Some of these limitations are due to TaskBridge being brand-new software, worked
on by one guy, in his spare time. However, many limitations come from the closed nature of the Apple ecosystem. This is
unfortunate,
but a reality.

You should therefore be aware of the following limitations:

## Notes

- Only image and URL attachments are supported. This is due to the closed way that other attachment
  types are handled by Apple Notes, and the fact that NextCloud notes do not support other attachment types.
- Todo items (i.e. items with a checkable box) are not supported, and will be converted to bullets once synchronised. This is
  due to the closed (and undocumented) way that Apple Notes handles these items.

## Reminders

- Alarms do not have time zone support.
- Although alarms are synchronised to NextCloud, the NextCloud Notes app will not display reminder messages. This is not a
  TaskBridge limitation.
- Additional notes added to reminders are synchronised, but this does not include attachments.

## Notes & Reminders

- When an item is sychronised from a remote server to the local Notes/Reminders app, the modification date of the local version
  is set to the date/time when sychronisation occurred. This cannot be changed by TaskBridge. This means that, on the next
  sync, the
  item will be re-uploaded to the remote server, even if no further changes have been made locally. However, this does not
  result in
  lost data - if more changes are made remotely, the remote note is correctly used as the 'newer' note.