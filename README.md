Sometimes the Mail system that Nerd.nu uses gets fouled up by duplicate entries in its `user` table. When two rows with the same username have completely different UUID mappings, things can break in unexpected ways.

How the duplicates happen is a partial mystery as of this writing, as there were quite a few that had accumulated over the years (mostly from the old CommandHelper version, before the Java rewrite), but one scenario that still works reliably is: connect to a server that is in "offline mode" but not behind a BungeeCord proxy. The server will happily assign a made-up UUID not recognized by Mojang, and then Mail will unwittingly insert the record into the database.

The following SQL query will identify problem records:

```
mysql> SELECT last_username, COUNT(*) c FROM user GROUP BY last_username HAVING c > 1;
+------------------+---+
| last_username    | c |
+------------------+---+
| some user        | 2 |
| some1else        | 2 |
| another          | 2 |
+------------------+---+
3 rows in set (0.05 sec)
```

Then you can dig further with something like this:

```
mysql> select * from user where last_display_name="redwall_hp";
+--------------------------------------+---------------+-------+-------------------+
| uuid                                 | last_username | email | last_display_name |
+--------------------------------------+---------------+-------+-------------------+
| 35d5de4b-5775-4b84-a47c-a5ae1126bb14 | redwall_hp    | NULL  | redwall_hp        |
| dc793933-68d0-30a9-98cb-33a44de69c35 | redwall_hp    | NULL  | redwall_hp        |
+--------------------------------------+---------------+-------+-------------------+
```

If you were to look up the UUIDs here on [NameMC](http://namemc.com), the first one would successfully find a valid Minecraft account matching the user redwall_hp. The second one, however, is a completely nonexistant UUID that was inserted by error.

To clean this stuff up, `nerdmailcleaner.py` builds a list of usernames with dupes, queries Mojang for the correct UUIDs matching the accounts, and deletes the duplicate rows. It might leave some behind if the users have since change their name, preventing the Mojang API from finding a UUID, but it will nab the vast majority of cases, leaving significantly less for final cleanup.


Usage
-----

Note: You probably want to create a new virtualenv before installing dependencies.

Copy `config.example.yml` to `config.yml` and fill-in the credentials for the mail database.

```
pip3 install -r requirements.txt
python3 nerdmailcleaner.py --dry
python3 nerdmailcleaner.py
```
