from datetime import timedelta
BROKER_URL = 'amqp://'
CELERY_RESULT_BACKEND = 'db+postgresql://ritesh@/ritesh'
CELERYBEAT_SCHEDULE = {
        'fetch-direct-messages-every-2min': {
            'task': 'tasks.fetchdms',
            'schedule': timedelta(minutes=2)
            },
        'check-if-follows-every2min': {
            'task': 'tasks.check_if_follows',
            'schedule': timedelta(minutes=2)
            },
        }
CELERY_TIMEZONE = 'UTC'
