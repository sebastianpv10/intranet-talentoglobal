from django.core.management.commands.runserver import Command as RunserverCommand


class Command(RunserverCommand):
    default_addr = "0.0.0.0"
    default_port = "8080"
