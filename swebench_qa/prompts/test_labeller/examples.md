# Examples

## Task 1

You will now consider the tests that will be used to check whether a given issue is resolved. The Gold Patch is the solution for the issue given in the original PR, and the Test Patch contains any new tests that were added in that same PR to verify that the issue was resolved. Please carefully study the issue, the test patch, and the gold patch shown below.

- Issue:
            
Title: Make URLValidator reject invalid characters in the username and password
Body: Description
         
                (last modified by Tim Bell)
         
Since #20003, core.validators.URLValidator accepts URLs with usernames and passwords. RFC 1738 section 3.1 requires "Within the user and password field, any ":", "@", or "/" must be encoded"; however, those characters are currently accepted without being %-encoded. That allows certain invalid URLs to pass validation incorrectly. (The issue originates in Diego Perini's ​gist, from which the implementation in #20003 was derived.)
An example URL that should be invalid is http://foo/bar@example.com; furthermore, many of the test cases in tests/validators/invalid_urls.txt would be rendered valid under the current implementation by appending a query string of the form ?m=foo@example.com to them.
I note Tim Graham's concern about adding complexity to the validation regex. However, I take the opposite position to Danilo Bargen about invalid URL edge cases: it's not fine if invalid URLs (even so-called "edge cases") are accepted when the regex could be fixed simply to reject them correctly. I also note that a URL of the form above was encountered in a production setting, so that this is a genuine use case, not merely an academic exercise.
Pull request: ​https://github.com/django/django/pull/10097


- Gold patch:

diff --git a/django/core/validators.py b/django/core/validators.py
--- a/django/core/validators.py
+++ b/django/core/validators.py
@@ -94,7 +94,7 @@ class URLValidator(RegexValidator):
 
     regex = _lazy_re_compile(
         r'^(?:[a-z0-9\.\-\+]*)://'  # scheme is validated separately
-        r'(?:\S+(?::\S*)?@)?'  # user:pass authentication
+        r'(?:[^\s:@/]+(?::[^\s:@/]*)?@)?'  # user:pass authentication
         r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
         r'(?::\d{2,5})?'  # port
         r'(?:[/?#][^\s]*)?'  # resource path


- Test patch:

diff --git a/tests/validators/invalid_urls.txt b/tests/validators/invalid_urls.txt
--- a/tests/validators/invalid_urls.txt
+++ b/tests/validators/invalid_urls.txt
@@ -57,3 +57,9 @@ http://example.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.
 http://example.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
 http://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaa
 https://test.[com
+http://foo@bar@example.com
+http://foo/bar@example.com
+http://foo:bar:baz@example.com
+http://foo:bar@baz@example.com
+http://foo:bar/baz@example.com
+http://invalid-.com/?m=foo@example.com

diff --git a/tests/validators/valid_urls.txt b/tests/validators/valid_urls.txt
--- a/tests/validators/valid_urls.txt
+++ b/tests/validators/valid_urls.txt
@@ -48,7 +48,7 @@ http://foo.bar/?q=Test%20URL-encoded%20stuff
 http://مثال.إختبار
 http://例子.测试
 http://उदाहरण.परीक्षा
-http://-.~_!$&'()*+,;=:%40:80%2f::::::@example.com
+http://-.~_!$&'()*+,;=%40:80%2f@example.com
 http://xn--7sbb4ac0ad0be6cf.xn--p1ai
 http://1337.net
 http://a.b-c.de

## Task 1 Result

The updated tests ensure the `URLValidator` rejects URLs with unencoded `":", "@", "/"` in usernames and passwords, confirming compliance with RFC 1738 by adding such invalid cases and correcting a valid URL to have encoded characters.

Score: 0 - The tests perfectly cover all possible solutions.

## Task 2

You will now consider the tests that will be used to check whether a given issue is resolved. The Gold Patch is the solution for the issue given in the original PR, and the Test Patch contains any new tests that were added in that same PR to verify that the issue was resolved. Please carefully study the issue, the test patch, and the gold patch shown below.

- Issue:
            
Title: SelectDateWidget can crash with OverflowError.
Body: Description

Given a relatively common view like this:
from django import forms
from django.forms import SelectDateWidget
from django.http import HttpResponse
class ReproForm(forms.Form):
         my_date = forms.DateField(widget=SelectDateWidget())
def repro_view(request):
         form = ReproForm(request.GET) # for ease of reproducibility
         if form.is_valid():
                 return HttpResponse("ok")
         else:
                 return HttpResponse("not ok")
# urls.py
urlpatterns = [path('repro/', views.repro_view, name='repro')]
A user can trigger a server crash, reproducible by running locally and visiting ​http://127.0.0.1:8000/repro/?my_date_day=1&my_date_month=1&my_date_year=1234567821345678, which results in
[...] - ERROR - django.request: Internal Server Error: /repro/
Traceback (most recent call last):
[...]
 File "[...]/site-packages/django/forms/widgets.py", line 1160, in value_from_datadict
        date_value = datetime.date(int(y), int(m), int(d))
OverflowError: signed integer is greater than maximum
This can be triggered similarly for a post request.
The issue happens as part of the validation logic run in form.is_valid, specifically, when calling the SelectDateWidget.value_from_datadict, where the user-controlled value is converted into a date without guarding against a possible OverflowError.
Specifically, y, m and d are user controlled, and the code does this:
 date_value = datetime.date(int(y), int(m), int(d)) 
When large integers (larger than sys.maxsize) are supplied to date's constructor it will throw an OverflowError:
>>> import datetime, sys
>>> datetime.date(sys.maxsize+1, 3, 4)
Traceback (most recent call last):
 File "<stdin>", line 1, in <module>
OverflowError: Python int too large to convert to C long

- Gold patch:

diff --git a/django/forms/widgets.py b/django/forms/widgets.py
--- a/django/forms/widgets.py
+++ b/django/forms/widgets.py
@@ -1161,6 +1161,8 @@ def value_from_datadict(self, data, files, name):
                 # Return pseudo-ISO dates with zeros for any unselected values,
                 # e.g. '2017-0-23'.
                 return "%s-%s-%s" % (y or 0, m or 0, d or 0)
+            except OverflowError:
+                return "0-0-0"
             return date_value.strftime(input_format)
         return data.get(name)
 
- Test patch:

diff --git a/tests/forms_tests/field_tests/test_datefield.py b/tests/forms_tests/field_tests/test_datefield.py
--- a/tests/forms_tests/field_tests/test_datefield.py
+++ b/tests/forms_tests/field_tests/test_datefield.py
@@ -1,3 +1,4 @@
+import sys
 from datetime import date, datetime
 
 from django.core.exceptions import ValidationError
@@ -36,6 +37,17 @@ def test_form_field(self):
         d = GetDate({"mydate_month": "1", "mydate_day": "1", "mydate_year": "2010"})
         self.assertIn('<label for="id_mydate_month">', d.as_p())
 
+        # Inputs raising an OverflowError.
+        e = GetDate(
+            {
+                "mydate_month": str(sys.maxsize + 1),
+                "mydate_day": "31",
+                "mydate_year": "2010",
+            }
+        )
+        self.assertIs(e.is_valid(), False)
+        self.assertEqual(e.errors, {"mydate": ["Enter a valid date."]})
+
     @translation.override("nl")
     def test_l10n_date_changed(self):
         \"\"\"
@@ -149,6 +161,8 @@ def test_datefield_1(self):
             f.clean("200a-10-25")
         with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
             f.clean("25/10/06")
+        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
+            f.clean("0-0-0")
         with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
             f.clean(None)
 
diff --git a/tests/forms_tests/widget_tests/test_selectdatewidget.py b/tests/forms_tests/widget_tests/test_selectdatewidget.py
--- a/tests/forms_tests/widget_tests/test_selectdatewidget.py
+++ b/tests/forms_tests/widget_tests/test_selectdatewidget.py
@@ -1,3 +1,4 @@
+import sys
 from datetime import date
 
 from django.forms import DateField, Form, SelectDateWidget
@@ -610,6 +611,7 @@ def test_value_from_datadict(self):
             ((None, "12", "1"), None),
             (("2000", None, "1"), None),
             (("2000", "12", None), None),
+            ((str(sys.maxsize + 1), "12", "1"), "0-0-0"),
         ]
         for values, expected in tests:
             with self.subTest(values=values):

## Task 2 Result

While the test covers all possible solutions, some unusual solutions that do not follow the standard overflow error message practice in the repository may be missed.

Score: 1 - The tests cover the majority of correct solutions, however some unusual solutions may be missed

## Task 3

You will now consider the tests that will be used to check whether a given issue is resolved. The Gold Patch is the solution for the issue given in the original PR, and the Test Patch contains any new tests that were added in that same PR to verify that the issue was resolved. Please carefully study the issue, the test patch, and the gold patch shown below.

- Issue: 

Title: Prevent using __isnull lookup with non-boolean value.
Body: __isnull should not allow for non-boolean values. Using truthy/falsey doesn't promote INNER JOIN to an OUTER JOIN but works fine for a simple queries. Using non-boolean values is ​undocumented and untested. IMO we should raise an error for non-boolean values to avoid confusion and for consistency.

- Gold patch:

diff --git a/django/db/models/lookups.py b/django/db/models/lookups.py
--- a/django/db/models/lookups.py
+++ b/django/db/models/lookups.py
@@ -1,5 +1,6 @@
 import itertools
 import math
+import warnings
 from copy import copy
 
 from django.core.exceptions import EmptyResultSet
@@ -9,6 +10,7 @@
 )
 from django.db.models.query_utils import RegisterLookupMixin
 from django.utils.datastructures import OrderedSet
+from django.utils.deprecation import RemovedInDjango40Warning
 from django.utils.functional import cached_property
 
 
@@ -463,6 +465,17 @@ class IsNull(BuiltinLookup):
     prepare_rhs = False
 
     def as_sql(self, compiler, connection):
+        if not isinstance(self.rhs, bool):
+            # When the deprecation ends, replace with:
+            # raise ValueError(
+            #     'The QuerySet value for an isnull lookup must be True or '
+            #     'False.'
+            # )
+            warnings.warn(
+                'Using a non-boolean value for an isnull lookup is '
+                'deprecated, use True or False instead.',
+                RemovedInDjango40Warning,
+            )
         sql, params = compiler.compile(self.lhs)
         if self.rhs:
             return "%s IS NULL" % sql, params

- Test patch:

diff --git a/tests/lookup/models.py b/tests/lookup/models.py
--- a/tests/lookup/models.py
+++ b/tests/lookup/models.py
@@ -96,3 +96,15 @@ class Product(models.Model):
 class Stock(models.Model):
     product = models.ForeignKey(Product, models.CASCADE)
     qty_available = models.DecimalField(max_digits=6, decimal_places=2)
+
+
+class Freebie(models.Model):
+    gift_product = models.ForeignKey(Product, models.CASCADE)
+    stock_id = models.IntegerField(blank=True, null=True)
+
+    stock = models.ForeignObject(
+        Stock,
+        from_fields=['stock_id', 'gift_product'],
+        to_fields=['id', 'product'],
+        on_delete=models.CASCADE,
+    )

diff --git a/tests/lookup/tests.py b/tests/lookup/tests.py
--- a/tests/lookup/tests.py
+++ b/tests/lookup/tests.py
@@ -9,9 +9,10 @@
 from django.db.models.expressions import Exists, OuterRef
 from django.db.models.functions import Substr
 from django.test import TestCase, skipUnlessDBFeature
+from django.utils.deprecation import RemovedInDjango40Warning
 
 from .models import (
-    Article, Author, Game, IsNullWithNoneAsRHS, Player, Season, Tag,
+    Article, Author, Freebie, Game, IsNullWithNoneAsRHS, Player, Season, Tag,
 )
 
 
@@ -969,3 +970,24 @@ def test_exact_query_rhs_with_selected_columns(self):
         ).values('max_id')
         authors = Author.objects.filter(id=authors_max_ids[:1])
         self.assertEqual(authors.get(), newest_author)
+
+    def test_isnull_non_boolean_value(self):
+        # These tests will catch ValueError in Django 4.0 when using
+        # non-boolean values for an isnull lookup becomes forbidden.
+        # msg = (
+        #     'The QuerySet value for an isnull lookup must be True or False.'
+        # )
+        msg = (
+            'Using a non-boolean value for an isnull lookup is deprecated, '
+            'use True or False instead.'
+        )
+        tests = [
+            Author.objects.filter(alias__isnull=1),
+            Article.objects.filter(author__isnull=1),
+            Season.objects.filter(games__isnull=1),
+            Freebie.objects.filter(stock__isnull=1),
+        ]
+        for qs in tests:
+            with self.subTest(qs=qs):
+                with self.assertWarnsMessage(RemovedInDjango40Warning, msg):
+                    qs.exists()

## Task 3 Result

The new test function `test_isnull_non_boolean_value` verifies that a deprecation warning of `RemovedInDjango40Warning` with a specific message is raised when performing a non-boolean `__isnull` operation. Any solution that implements some other error message  and/or deprecation class will easily fail the tests.

Score: 2 - The tests work but some perfectly reasonable solutions may be missed by the tests

## Task 4

You will now consider the tests that will be used to check whether a given issue is resolved. The Gold Patch is the solution for the issue given in the original PR, and the Test Patch contains any new tests that were added in that same PR to verify that the issue was resolved. Please carefully study the issue, the test patch, and the gold patch shown below.

- Issue:

Title: Documentation: hypercorn and static files
Body: Coming from the age-old problem of service static files, the usual process looks like this:

1) ✅develop and test using  manage.py runserver  and everything just works fine
2) ✅ deploy code using WSGI or ASGI as described in the docs
3) ❌ find out that static files are missing

Specifically referring to ​https://docs.djangoproject.com/en/3.1/howto/deployment/asgi/hypercorn/

As there is a dedicated documentation page for hypercorn, it doesn't look like there's a need for thinking of serving static files.

A friend of mine suggested to use whitenoise: ​https://github.com/evansd/whitenoise

Would it make sense to integrate this into the Django docs?

To be transparent here, I started also different threads on different channels but it seems like nobody really wants to tackle this issue, so I thought addressing the issue at least via Django sounds reasonable because it's a Web framework:
here: ​https://softwarerecs.stackexchange.com/questions/77600/simple-and-secure-command-line-http-server
and there: ​https://gitlab.com/pgjones/hypercorn/-/issues/173
from another guy: ​https://gitlab.com/pgjones/hypercorn/-/issues/45

As of now, I addressed my real-world setup by setting up a "mini"-nginx for now, serving static files and proxying hypercorn, but that does not feel like a holistic solution; also when it comes to automated deployment, permissions, principles such as "test as you fly, fly as you test" etc. it's a lot more brittle.

- Gold patch:

diff --git a/django/conf/__init__.py b/django/conf/__init__.py
--- a/django/conf/__init__.py
+++ b/django/conf/__init__.py
@@ -9,10 +9,12 @@
 import importlib
 import os
 import time
+import warnings
 from pathlib import Path
 
 from django.conf import global_settings
 from django.core.exceptions import ImproperlyConfigured
+from django.utils.deprecation import RemovedInDjango50Warning
 from django.utils.functional import LazyObject, empty
 
 ENVIRONMENT_VARIABLE = "DJANGO_SETTINGS_MODULE"
@@ -157,6 +159,14 @@ def __init__(self, settings_module):
                 setattr(self, setting, setting_value)
                 self._explicit_settings.add(setting)
 
+        if self.USE_TZ is False and not self.is_overridden('USE_TZ'):
+            warnings.warn(
+                'The default value of USE_TZ will change from False to True '
+                'in Django 5.0. Set USE_TZ to False in your project settings '
+                'if you want to keep the current default behavior.',
+                category=RemovedInDjango50Warning,
+            )
+
         if hasattr(time, 'tzset') and self.TIME_ZONE:
             # When we can, attempt to validate the timezone. If we can't find
             # this file, no check happens and it's harmless.

- Test patch:

diff --git a/tests/settings_tests/tests.py b/tests/settings_tests/tests.py
--- a/tests/settings_tests/tests.py
+++ b/tests/settings_tests/tests.py
@@ -13,6 +13,7 @@
 )
 from django.test.utils import requires_tz_support
 from django.urls import clear_script_prefix, set_script_prefix
+from django.utils.deprecation import RemovedInDjango50Warning
 
 
 @modify_settings(ITEMS={
@@ -332,6 +333,21 @@ def test_incorrect_timezone(self):
         with self.assertRaisesMessage(ValueError, 'Incorrect timezone setting: test'):
             settings._setup()
 
+    def test_use_tz_false_deprecation(self):
+        settings_module = ModuleType('fake_settings_module')
+        settings_module.SECRET_KEY = 'foo'
+        sys.modules['fake_settings_module'] = settings_module
+        msg = (
+            'The default value of USE_TZ will change from False to True in '
+            'Django 5.0. Set USE_TZ to False in your project settings if you '
+            'want to keep the current default behavior.'
+        )
+        try:
+            with self.assertRaisesMessage(RemovedInDjango50Warning, msg):
+                Settings('fake_settings_module')
+        finally:
+            del sys.modules['fake_settings_module']
+
 
 class TestComplexSettingOverride(SimpleTestCase):
     def setUp(self):
@@ -398,6 +414,7 @@ def test_configure(self):
     def test_module(self):
         settings_module = ModuleType('fake_settings_module')
         settings_module.SECRET_KEY = 'foo'
+        settings_module.USE_TZ = False
         sys.modules['fake_settings_module'] = settings_module
         try:
             s = Settings('fake_settings_module')

diff --git a/tests/test_sqlite.py b/tests/test_sqlite.py
--- a/tests/test_sqlite.py
+++ b/tests/test_sqlite.py
@@ -29,3 +29,5 @@
 ]
 
 DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
+
+USE_TZ = False

## Task 4 Result

The tests address something different than the issue description (tests for internalization) while the issue is about serving static file. Generally i dont think this should have a test case.