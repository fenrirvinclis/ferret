from tweepy import API, Cursor

from tweepy.utils import import_simplejson, urlencode_noplus
json = import_simplejson()


class Follow():
    def __init__(self, auth):
        self.auth = auth
        self.api = API(self.auth)

    def autofollow(self):
        """
        Auto follow everyone who follows us
        """
        # poor man's DB, move to SQLite or something enterprise-y at some point
        self.whitelist = []
        with open('whitelist.txt') as f:
            for line in f:
                a = f.read().strip()
                self.whitelist.append(a)

        for follower in Cursor(self.api.followers()).items():
            if follower.screen_name in self.whitelist:
                self.api.create_friendship(follower)
                # We need to wait before sending a DM as this may not be instantaneous

    def follow(self, user):
        """
        Follow a user, just calls the API but we may want to do other things before that.
        """
        self.api.create_friendship(user)

    def unfollow(self, users):
        """
        Don't care if we're friends or not, we just destroy friendships :(
        """
        for user in users:
            self.api.destroy_friendship(user)

    def my_followers(self):
        """
        Return my followers
        """
        for follower in self.api.followers(self.auth.get_username()):
            print follower.screen_name

