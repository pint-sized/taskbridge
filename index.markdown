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
2. Unfortunately, the way that Apple Notes and Reminders are built makes them quite difficult to interact with programmatically.
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
is the same as the username you use to login to NextCloud. For CalDAV, enter your username (this could also be your email 
address).

If you set the server type to NextCloud, the **Tasks Path** field will auto-complete as you type your username. You don't 
need to change this, most of the time. 

![Autocompleting remote reminder login](images/110_reminders_autocomplete.png)

Fill in the rest of the fields. 

- **Server Address**: The address of your server. For example, _`https://nextcloud.mydomain.com`_.
- **Password**: The password for your server. For NextCloud, this is the same password you use to login to NextCloud.

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
list which doesn't have an associated NextCloud/CalDAV calendar, the calendar will be created before reminders/tasks are synced. 
Similarly, deletions are also synchronised; for example, if you delete the tasks calendar _Work_, and you've chosen for it to be 
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

To run the CLI, use 

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
on by one guy, in his spare time. However, many limitations come from the closed nature of the Apple ecosystem. This is unfortunate, 
but a reality. 

You should therefore be aware of the following limitations:

## Notes
- Only image and URL attachments are supported. This is due to the closed way that other attachment
types are handled by Apple Notes, and the fact that NextCloud notes do not support other attachment types.
- Todo items (i.e. items with a checkable box) are not supported, and will be converted to bullets once synchronised. This is 
due to the closed (and undocumented) way that Apple Notes handles these items.

## Reminders
- Alarms do not have time zone support.
- Although alarms are synchronised to NextCloud, the NextCloud Notes app will not display reminder messages. This is not a TaskBridge limitation.
- Additional notes added to reminders are synchronised, but this does not include attachments. 

## Notes & Reminders
- When an item is sychronised from a remote server to the local Notes/Reminders app, the modification date of the local version 
is set to the date/time when sychronisation occurred. This cannot be changed by TaskBridge. This means that, on the next sync, the 
item will be re-uploaded to the remote server, even if no further changes have been made locally. However, this does not result in 
lost data - if more changes are made remotely, the remote note is correctly used as the 'newer' note.