#!/usr/bin/env python3
import sys, time, uuid, argparse, yaml, requests
import pymysql.cursors


class NerdMailCleaner:


    def __init__(self, args):
        self.args = args
        self.readConfig()
        self.openDatabase()
        self.loadUsers()
        self.process()
        self.db.close()


    # Load the configuration from disk
    def readConfig(self):
        with open("config.yml", 'r') as stream:
            try:
                self.config = yaml.load(stream)
            except yaml.YAMLError as ex:
                print(ex)
                sys.exit(1)


    # Connect to the database
    def openDatabase(self):
        try:
            cursor = pymysql.cursors.DictCursor
            self.db = pymysql.connect(
                    host=self.config['db']['host'],
                    user=self.config['db']['user'],
                    password=self.config['db']['password'],
                    db=self.config['db']['database'],
                    cursorclass=cursor)
        except pymysql.err.OperationalError as ex:
            print(ex)
            sys.exit(1)


    # Build a list of user names that have more than one UUID pairing.
    # This is a major cause of problems for the Mail system, and is often
    # the result of connecting to an offline mode server that isn't behind
    # a BungeeCord instance, as the game makes up non-registered UUIDs.
    def loadUsers(self):
        with self.db.cursor() as cursor:
            sql = "SELECT last_username, COUNT(*) count FROM user GROUP BY last_username HAVING count > 1;"
            cursor.execute(sql)
            self.users = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) as count from user;")
            count = cursor.fetchone()['count']
            print("Found {0} users with duplicate UUID/name pairings from {1} total users.".format(len(self.users), count))


    # Chunk users into groups of 100 to stay within Mojang's API limit.
    def splitRequestBatches(self):
        batches = []
        for i in range(0, len(self.users), 100):
            chunk = []
            for j in self.users[i:i + 100]:
                chunk.append(j['last_username'])
            batches.append(chunk)
        return batches


    # Hit the Mojang API and return a list of UUIDs for the requested names.
    # The API will ignore names that don't currently point to a valid user.
    def getUUIDsFromNames(self, users):
        url = "https://api.mojang.com/profiles/minecraft"
        postdata = []
        for user in users:
            postdata.append(user)
        r = requests.post(url, json=postdata)
        if r.status_code is not requests.codes.ok:
            return None
        return r.json()


    # Search a list of dictionaries for an entry where "key" is equal to "val"
    def findEntry(self, l, key, val):
        for i in l:
            if key in i and i[key].lower() == val.lower():
                return i
        return None


    # Actually remove the duplicate record from the database
    def removeDuplicate(self, name, idStr):
        with self.db.cursor() as cursor:
            cursor.execute("SELECT uuid, last_username FROM user WHERE last_username = %s;", name)
            entries = cursor.fetchall()
            for entry in entries:
                if entry['uuid'] == idStr:
                    entries.remove(entry)
        for entry in entries:
            print("{0}\t{1}".format(entry['uuid'], entry['last_username']))
            if not self.args.dry:
                with self.db.cursor() as cursor:
                    cursor.execute("DELETE from user WHERE uuid = %s;", entry['uuid'])
                self.db.commit()


    # Batch the results into groups and perform the operations
    def process(self):
        batches = self.splitRequestBatches()
        for batch in batches:
            print("Processing batch {0}/{1}".format(batches.index(batch)+1, len(batches)))
            time.sleep(2) #throttle requests
            uuids = self.getUUIDsFromNames(batch)
            if uuids is None or len(uuids) < 1:
                print("Batch #{0} failure. Could not retrieve UUIDs.".format(batches.index(batch)))
                print("Skipped: " + ", ".join(batch))
                continue
            for name in batch:
                mojang = self.findEntry(uuids, "name", name)
                if mojang is not None:
                    idStr = str(uuid.UUID(mojang['id']))
                    self.removeDuplicate(name, idStr)




if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Dry run. Won't update database.")
    args = parser.parse_args()
    if (args.dry):
        print("Performing dry run. The database will not be written to.")
    nmc = NerdMailCleaner(args)
