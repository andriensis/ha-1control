DOMAIN = "onecontrol"


# 1Control's Firebase Web API key, reverse-engineered from the official mobile app.
# Not a secret — scoped to user-level auth only (sign in/sign up/token refresh).
# No admin, Firestore, FCM, or broad Google API access. Safe to store in source.
FIREBASE_API_KEY = "AIzaSyAfwZUW5HAbDmA1KJxA4-6n3yeq2eBH5KA"
FIREBASE_AUTH_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)
FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"

# 1Control's Cloud Endpoints API key, reverse-engineered from the official mobile app.
# Required as ?key= on every backend request. Without a valid Firebase Bearer token
# the backend returns 401, so this key alone grants no data access. Safe to store in source.
BACKEND_API_KEY = "AIzaSyDt90BzaVvT167H7t2o7QXZHnAjb-EClGw"
API_BASE_URL = "https://onecontrolcloud.appspot.com/_ah/api/webAdmin/v1"

CONF_DEVICES = "devices"
CONF_UID = "uid"
CONF_AUTO_CLOSE_DELAY = "auto_close_delay"

# Seconds before HA marks the gate as closed again after an open command.
# RF gates auto-close on their own; this keeps HA state in sync.
AUTO_CLOSE_DELAY = 10
