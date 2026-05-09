source activate drug4
NUM_WORKERS=3
TIMEOUT=420
PIDFILE=gunicorn.pid
ACCESS_LOG=gunicorn-access.log
ERROR_LOG=gunicorn-error.log 
LOG_LEVEL=error
exec gunicorn app:app \
--workers $NUM_WORKERS \
--timeout $TIMEOUT \
--log-level=$LOG_LEVEL \
--bind=0.0.0.0:5333 \
--pid=$PIDFILE \
--error-logfile=$ERROR_LOG \
--access-logfile=$ACCESS_LOG \
--daemon
