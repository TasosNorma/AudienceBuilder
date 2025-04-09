default_args = {
    'owner': 'audiencebuilder',
    'depends_on_past': False, #It doesn't depend on any past dag to finish so that it can run
    'email_on_failure': False, #We don't want to send emails on failure
    'email_on_retry': False, #We don't want to send emails on retry
    'retries': 0 #We don't want to retry the task
}