DOMAIN = "onecontrol"

FIREBASE_API_KEY = "AIzaSyAfwZUW5HAbDmA1KJxA4-6n3yeq2eBH5KA"
FIREBASE_AUTH_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)
FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"

# Backend (Cloud Endpoints) API key — required as ?key= on every request
BACKEND_API_KEY = "AIzaSyDt90BzaVvT167H7t2o7QXZHnAjb-EClGw"
API_BASE_URL = "https://onecontrolcloud.appspot.com/_ah/api/webAdmin/v1"

CONF_DEVICES = "devices"
CONF_UID = "uid"
CONF_AUTO_CLOSE_DELAY = "auto_close_delay"

# Seconds before HA marks the gate as closed again after an open command.
# RF gates auto-close on their own; this keeps HA state in sync.
AUTO_CLOSE_DELAY = 10
