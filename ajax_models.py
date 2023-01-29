from django.shortcuts import HttpResponse
from django.http import HttpResponseBadRequest
from django.views.generic import FormView
import json


class AjaxFormMixin(FormView):

    template_name = 'form_ajax.html'

    def form_valid(self, form):
        form.save()
        return HttpResponse('OK')

    def form_invalid(self, form):
        errors_dict = json.dumps(dict([(k, [e for e in v]) for k, v in form.errors.items()]))
        return HttpResponseBadRequest(json.dumps(errors_dict))