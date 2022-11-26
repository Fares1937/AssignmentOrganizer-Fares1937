from mainapp import services
from django_daemon_command.management.base import DaemonCommand

# this class initializes the email service alone for a separate daemon
class Command(DaemonCommand):

    initialized = False
    def process(self, *args, **options):
        '''
        Initializes email service for Heroku Daemon
        '''
        if not self.initialized:
            print("Initializing dyno services...")
            services.initialize_services_for_daemon()
            print("Services initialized")
            self.initialized = True