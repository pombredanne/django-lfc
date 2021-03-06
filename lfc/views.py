# python imports
import logging
import sys
import traceback

# django imports
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

# lfc imports
import lfc.utils
from lfc.utils import MessageHttpResponseRedirect
from lfc.models import File
from lfc.models import BaseContent
from lfc.models import Portal
from lfc.settings import LFC_LANGUAGE_IDS

# tagging imports
from tagging.models import TaggedItem
from tagging.utils import get_tag

# Load logger
logger = logging.getLogger("default")


def portal(request, template_name="lfc/portal.html"):
    """
    Displays the portal.
    """
    return render_to_response(template_name, RequestContext(request, {
        "portal": lfc.utils.get_portal()
    }))


def base_view(request, language=None, slug=None, obj=None):
    """Displays the object for given language and slug.
    """
    if language:
        if language not in LFC_LANGUAGE_IDS:
            raise Http404
        translation.activate(language)
    else:
        translation.activate(settings.LANGUAGE_CODE)

    if slug:
        obj = lfc.utils.traverse_object(request, slug)
    else:
        the_portal = lfc.utils.get_portal()
        if the_portal.standard:
            obj = lfc.utils.get_content_object(portal=the_portal)
            if obj.language != language:
                if obj.is_canonical():
                    t = obj.get_translation(request, language)
                    if t:
                        obj = t
                else:
                    canonical = obj.get_canonical(request)
                    if canonical:
                        obj = canonical
        else:
            obj = the_portal

    request.META["lfc_context"] = obj

    language = translation.get_language()
    # If the given language is the default language redirect to the url without
    # the language code http:/domain.de/de/hurz = http:/domain.de/hurz

    if obj is None:
        raise Http404()

    if isinstance(obj, Portal):
        return portal(request)

    if lfc.utils.registration.get_info(obj) is None:
        raise Http404()

    if not obj.is_active(request.user):
        raise Http404()

    if not obj.has_permission(request.user, "view"):
        return HttpResponseRedirect(reverse("lfc_login"))

    # Redirect to standard object unless superuser is asking
    if obj.standard and request.user.is_superuser == False:
        url = obj.get_absolute_url()
        return HttpResponseRedirect(url)

    obj.set_context(request)
    result = obj.render(request)
    return HttpResponse(result)


def file(request, language=None, id=None):
    """Delivers files to the browser.
    """
    file = get_object_or_404(File, pk=id)
    response = HttpResponse(file.file, mimetype='application/binary')
    response['Content-Disposition'] = 'attachment; filename=%s' % file.title

    return response


def live_search_results(request, language=None, template_name="lfc/live_search_results.html"):
    """Displays the live search result for passed language and query.
    """
    query = request.GET.get("q")

    if language is None:
        language = settings.LANGUAGE_CODE

    f = Q(exclude_from_search=False) & \
        (Q(language=language) | Q(language="0")) & \
        (Q(searchable_text__icontains=query))

    try:
        obj = BaseContent.objects.get(slug="search-results")
    except BaseContent.DoesNotExist:
        obj = None

    results = lfc.utils.get_content_objects(request, f)
    quantity = len(results)

    return render_to_response(template_name, RequestContext(request, {
        "lfc_context": obj,
        "query": query,
        "results": results[:20],
        "quantity": quantity,
        "see_all": quantity > 20,
    }))


def search_results(request, language=None, template_name="lfc/search_results.html"):
    """Displays the search result for passed language and query.
    """
    query = request.GET.get("q")

    if language is None:
        language = settings.LANGUAGE_CODE

    f = Q(exclude_from_search=False) & \
        (Q(language=language) | Q(language="0")) & \
        (Q(searchable_text__icontains=query))

    try:
        obj = BaseContent.objects.get(slug="search-results")
    except BaseContent.DoesNotExist:
        obj = None

    results = lfc.utils.get_content_objects(request, f)

    return render_to_response(template_name, RequestContext(request, {
        "lfc_context": obj,
        "query": query,
        "results": results,
    }))


def set_language(request, language, id=None):
    """Sets the language to the given language

    parameters:

        - language
          the requested language

        - id:
          the id of the current displayed object
    """
    translation.activate(language)

    url = None
    if id:
        obj = BaseContent.objects.get(pk=id)

        # If the language of the current object same as the requested language we
        # just stay on the object.
        if obj.language == language:
            url = obj.get_absolute_url()

        # Coming from a object with neutral language, we stay on this object
        # but switch to the request language.
        elif obj.language == "0":
            url = obj.get_absolute_url()

        # Coming from a canonical object, we try to get the translation for the
        # given language
        elif obj.is_canonical():
            t = obj.get_translation(request, language)
            if t:
                url = t.get_absolute_url()
            else:
                if language == settings.LANGUAGE_CODE:
                    url = "/"
                else:
                    url = "/" + language

        # Coming from a translation, we try to get the canonical and display
        # the given language
        else:
            canonical = obj.get_canonical(request)
            if canonical:
                translated = canonical.get_translation(request, language)
                if translated:
                    url = translated.get_absolute_url()
                else:
                    url = canonical.get_absolute_url()
            else:
                if language == settings.LANGUAGE_CODE:
                    url = "/"
                else:
                    url = "/" + language
    else:
        portal = lfc.utils.get_portal()
        if language == settings.LANGUAGE_CODE:
            url = "/"
        else:
            url = "/" + language

    response = HttpResponseRedirect(url)

    if translation.check_for_language(language):
        if hasattr(request, 'session'):
            request.session['django_language'] = language
        else:
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)

    return response


def lfc_tagged_object_list(request, slug, tag, template_name="lfc/page_list.html"):
    """
    """
    if tag is None:
        raise AttributeError(_('tagged_object_list must be called with a tag.'))

    tag_instance = get_tag(tag)
    if tag_instance is None:
        raise Http404(_('No Tag found matching "%s".') % tag)

    obj = request.META.get("lfc_context")
    queryset = BaseContent.objects.filter(parent=obj)
    objs = TaggedItem.objects.get_by_model(queryset, tag_instance)

    return render_to_response(template_name, RequestContext(request, {
        "slug": slug,
        "lfc_context": obj,
        "objs": objs,
        "tag": tag,
    }))


def fiveohoh(request, template_name="500.html"):
    """Handler for 500 server errors. Mails the error to ADMINS.
    """
    exc_type, exc_info, tb = sys.exc_info()
    response = "%s\n" % exc_type.__name__
    response += "%s\n" % exc_info
    response += "TRACEBACK:\n"
    for tb in traceback.format_tb(tb):
        response += "%s\n" % tb

    response += "\nREQUEST:\n%s" % request

    try:
        from_email = settings.ADMINS[0][1]
        to_emails = [a[1] for a in settings.ADMINS]
    except IndexError:
        pass
    else:
        try:
            portal = lfc.utils.get_portal()
            name = portal.title
        except:
            name = "LFC"

        mail = EmailMessage(
            subject="Error %s" % name, body=response, from_email=from_email, to=to_emails)
        mail.send(fail_silently=True)

    return base_view(request, slug="500")
