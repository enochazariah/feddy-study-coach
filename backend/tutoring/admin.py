from django.contrib import admin

from .models import AgentRun, Conversation, LearningSession, Message, Subject, Topic

admin.site.register(Subject)
admin.site.register(Topic)
admin.site.register(LearningSession)
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(AgentRun)
