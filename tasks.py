from celery import Celery
import binascii, os
import tweepy
import settings
import utils
import dmhandlers
import psycopg2
from tweepy import TweepError
from email.mime.text import MIMEText
from settings import EMAIL_ADDRESS, SMTP_SERVER
import smtplib
from psycopg2 import ProgrammingError

app = Celery('ferret_tasks')
app.config_from_object('celeryconfig')
conn = psycopg2.connect(settings.PGDBNAME)
conn.autocommit = True

def _get_api():
    auth = tweepy.OAuthHandler(settings.CONSUMER_KEY, settings.CONSUMER_SECRET)
    auth.set_access_token(settings.ACCESS_TOKEN, settings.ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    return api

def get_cursor():
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1")
    except ProgrammingError as p:
        print "Programming error", p
        cur.rollback()
    return cur


def _get_sinceid(name):
    cur = get_cursor()
    cur.execute("SELECT value FROM SINCEID WHERE name = %s", (name,))
    r = cur.fetchone()
    conn.commit()
    if r is not None:
        return r[0]
    else:
        return 0


def _set_sinceid(name, sinceid):
    cur = conn.cursor()
    cur.execute("UPDATE SINCEID SET value = %s WHERE name = %s",
                (sinceid, name,))
    conn.commit()


@app.task
def refresh_followers():
    api = _get_api()
    cur = get_cursor()
    try:
        for user in tweepy.Cursor(api.followers, screen_name="CigiBot").items():
            # print"[i]Inserting ---------"
            # print user.id
            #print user.screen_name
            cur.execute("""INSERT INTO FOLLOWER (id,screen_name) SELECT %s, %s WHERE
                NOT EXISTS (SELECT id FROM FOLLOWER WHERE id = %s)""", (str(user.id), user.screen_name, str(user.id)))
            conn.commit()
    except TweepError as err:
        raise refresh_followers.retry(countdown=60*3, exc=err)


@app.task
def check_if_follows():
    api = _get_api()
    for user in tweepy.Cursor(api.followers, screen_name="CigiBot").items():
        print user.screen_name



@app.task
def fetchdms():
    api = _get_api()
    hits = utils.get_hits_left(api.rate_limit_status(), 'direct_messages',
                               '/direct_messages')
    if hits < 1:
        return
    #messages = None
    sinceid = _get_sinceid('dm_sinceid')
    try:
        messages = api.direct_messages(since_id=sinceid)
    except TweepError as err:
        print "Failed to fetch DMs", err
        # Retry in four minutes if we fail
        # raise fetchdms.retry(countdown=60*4, exc=err)
    if len(messages) is not 0:
        dmhandlers.DmCommandHandler(messages)
        _set_sinceid('dm_sinceid', messages[0].id)
    else:
        print "No new DMs yet!"
    return True


@app.task
def send_dm(to, message):
    # TODO: Handle fails by saving to DB ?
    api = _get_api()
    try:
        api.send_direct_message(screen_name=to, text=message)
    except TweepError as err:
        print "Failed to send %s to %s" % (message, to)
        print err
        #TODO: Exponential back-off, for now retry after 180 seconds
        #raise send_dm.retry(countdown=60*3, exc=err)


@app.task
def update_status(message):
    try:
        #status = "@%s %s" % (to, message[:140])
        #print status
        api = _get_api()
        api.update_status(message)
    except TweepError as err:
        print "Failed to update status, retrying in 180 seconds", err
        #TODO: Exponential back-off, for now retry after 180 seconds
        #raise update_status.retry(countdown=60*3, exc=err)


@app.task
def link_user(email, twitter_handle):
    """
    Allow users to claim twitter IDs
    if they say I am rksinha, then the DM sender is mapped to that twitter ID
    """
    cur = get_cursor()

    cur.execute("SELECT email FROM VERIFIED WHERE LOWER(email) = LOWER(%s) AND VERIFIED = FALSE", (email,))
    print "Trying to verify %s" % (email,)
    r = cur.fetchone()
    if r is not None:
        # random code for auth
        code = binascii.b2a_hex(os.urandom(4))
        # we might have dupe codes!! Random number generators are not to be trusted.
        cur = get_cursor()
        cur.execute("UPDATE VERIFIED SET twitter_handle = %s, CODE = %s WHERE LOWER(email) = LOWER(%s)",
                    (twitter_handle, code, email,))
        conn.commit()
        update_status.delay("%s I've sent you a code, check your email" % (twitter_handle,))
        msg = """Hello %s,\nEither you, or someone claiming to be you, asked to link a Twitter account. If you are the
        owner of @%s, please send a direct message to @cigibot with the following code:\n\n%s""" \
              % (email, twitter_handle, twitter_handle, code)
        send_email.delay(email + "@cigital.com", "Your cigibot code", msg)
    else:
        print email, ":No such email_address or user has verified already!"
        return


@app.task
def check_auth_code(twitter_handle, code):
    """
    Test if twitter handle has the authcode
    :param twitter_handle: The twitter handle that sent us the code
    :param code: the code we have in DB
    :return:
    """
    print "Checking auth for %s - %s" % (twitter_handle, code,)
    cur = get_cursor()

    cur.execute("SELECT LOWER(email) from VERIFIED WHERE code = %s AND twitter_handle = %s", (code, twitter_handle, ))
    result = cur.fetchone()
    conn.commit()
    #No results!
    if result is None:
        # Do nothing if we have a bad code
        return
    cur = get_cursor()
    cur.execute("UPDATE VERIFIED SET verified = TRUE WHERE twitter_handle = %s", (twitter_handle,))
    conn.commit()
    update_status.delay("Congratulations @%s, and welcome to swsec land!" % (twitter_handle,))


@app.task
def send_email(to, subject, message):
    """
    Send email using the tech ferret's gmail account
    :param to: The recipient
    :param subject: The subject of the email
    :param message: The message
    :return:
    """
    #TODO: Add checks to stop spamming people limit 3?!
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to
    session = smtplib.SMTP(SMTP_SERVER, '25')
    #TODO: Retry if we fail?
    session.ehlo()
    session.sendmail(EMAIL_ADDRESS, to, msg.as_string())

if __name__ == '__main__':
    print "Testing!"
