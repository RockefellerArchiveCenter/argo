from django.http import Http404
from django_elasticsearch_dsl_drf.pagination import LimitOffsetPagination
from elasticsearch_dsl import A, Q
from rac_es.documents import (Agent, BaseDescriptionComponent, Collection,
                              Object, Term)
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from .pagination import CollapseLimitOffsetPagination
from .serializers import (AgentListSerializer, AgentSerializer,
                          CollectionHitSerializer, CollectionListSerializer,
                          CollectionSerializer, FacetSerializer,
                          ObjectListSerializer, ObjectSerializer,
                          TermListSerializer, TermSerializer)
from .view_helpers import (FILTER_BACKENDS, NUMBER_LOOKUPS, SEARCH_BACKENDS,
                           STRING_LOOKUPS, SearchMixin)


class DocumentViewSet(SearchMixin, ReadOnlyModelViewSet):
    filter_backends = FILTER_BACKENDS
    pagination_class = LimitOffsetPagination

    def get_serializer_class(self):
        if self.action == "list":
            try:
                return self.list_serializer
            except AttributeError:
                return self.serializer
        return self.serializer

    def get_queryset(self):
        """Returns only certain fields to improve performance of list views."""
        query = self.search.query()
        if self.action == "list":
            query = query.source(self.list_fields)
        return query

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        queryset = self.get_queryset().filter(
            "match_phrase", **{"_id": self.kwargs[lookup_url_kwarg]}
        )
        hits = queryset.execute().hits
        count = len(hits)
        if count != 1:
            message = (
                "No object matches the given query."
                if count == 0
                else "Multiple results matches the given query. Expected a single result."
            )
            raise Http404(message)
        else:
            obj = hits[0]
            return obj

    @property
    def list_fields(self):
        return list(set(list(self.filter_fields) + list(self.ordering_fields) + list(self.search_fields) + ["type", "dates"]))


class AgentViewSet(DocumentViewSet):
    """
    Returns data about agents, including people, organizations and families.
    """

    document = Agent
    list_serializer = AgentListSerializer
    serializer = AgentSerializer
    relations = ("collections", "objects")

    filter_fields = {
        "title": {"field": "title.keyword", "lookups": STRING_LOOKUPS, },
        "agent_type": {"field": "agent_type", "lookups": STRING_LOOKUPS, },
        "start_date": {"field": "dates.begin", "lookups": NUMBER_LOOKUPS, },
        "end_date": {"field": "dates.end", "lookups": NUMBER_LOOKUPS, },
    }

    search_fields = ("title", "description")
    search_nested_fields = {
        "notes": {"path": "notes", "fields": ["subnotes.content"]},
    }

    ordering_fields = {
        "title": "title.keyword",
        "type": "type.keyword",
        "start_date": "dates.begin",
        "end_date": "dates.end",
    }


class CollectionViewSet(DocumentViewSet):
    """
    Returns data about collections, or intellectually significant groups of archival records.
    """

    document = Collection
    list_serializer = CollectionListSerializer
    serializer = CollectionSerializer

    filter_fields = {
        "title": {"field": "title.keyword", "lookups": STRING_LOOKUPS, },
        "start_date": {"field": "dates.begin", "lookups": NUMBER_LOOKUPS, },
        "end_date": {"field": "dates.end", "lookups": NUMBER_LOOKUPS, },
        "level": {"field": "level.keyword", "lookups": STRING_LOOKUPS, },
    }

    search_fields = ("title",)
    search_nested_fields = {
        "notes": {"path": "notes", "fields": ["subnotes.content"]},
    }

    ordering_fields = {
        "title": "title.keyword",
        "level": "level.keyword",
        "start_date": "dates.begin",
        "end_date": "dates.end",
    }

    def get_object(self):
        obj = super(CollectionViewSet, self).get_object()
        if self.request.GET.get("query"):
            query = self.request.GET["query"]
            for c in obj.children:
                q = Q("bool",
                      should=[
                          Q("nested", path="notes", query=Q("match", notes__subnotes__content=query)),
                          Q("match", title=query)],
                      must=[Q("nested", path="ancestors", query=Q("match", ancestors__identifier=c.identifier))],
                      minimum_should_match=1)
                self.search.query = q
                c.hit_count = self.search.query().count()
        return obj


class ObjectViewSet(DocumentViewSet):
    """
    Returns data about objects, or groups of archival records which have no children.
    """

    document = Object
    list_serializer = ObjectListSerializer
    serializer = ObjectSerializer

    filter_fields = {
        "title": {"field": "title.keyword", "lookups": STRING_LOOKUPS, },
        "start_date": {"field": "dates.begin", "lookups": NUMBER_LOOKUPS, },
        "end_date": {"field": "dates.end", "lookups": NUMBER_LOOKUPS, },
    }

    search_fields = ("title",)
    search_nested_fields = {
        "notes": {"path": "notes", "fields": ["subnotes.content"]},
    }

    ordering_fields = {
        "title": "title.keyword",
        "start_date": "dates.begin",
        "end_date": "dates.end",
    }


class TermViewSet(DocumentViewSet):
    """
    Returns data about terms, including subjects, geographic areas and more.
    """

    document = Term
    list_serializer = TermListSerializer
    serializer = TermSerializer

    filter_fields = {
        "title": {"field": "title.keyword", "lookups": STRING_LOOKUPS, },
        "term_type": {"field": "term_type", "lookups": STRING_LOOKUPS, },
    }

    search_fields = ("title", "type")

    ordering_fields = {
        "title": "title.keyword",
    }


class SearchView(DocumentViewSet):
    """Performs search queries across agents, collections, objects and terms."""
    document = BaseDescriptionComponent
    list_serializer = CollectionHitSerializer
    pagination_class = CollapseLimitOffsetPagination
    filter_backends = SEARCH_BACKENDS

    filter_fields = {
        "category": {"field": "category", "lookups": STRING_LOOKUPS},
        "end_date": {"field": "dates.end", "lookups": NUMBER_LOOKUPS},
        "genre": {"field": "formats", "lookups": STRING_LOOKUPS},
        "online": "online",
        "start_date": {"field": "dates.begin", "lookups": NUMBER_LOOKUPS},
        "type": {"field": "type", "lookups": STRING_LOOKUPS},
    }
    nested_filter_fields = {
        "subject": {
            "field": "terms.title.keyword",
            "path": "terms",
        },
        "creator": {
            "field": "creators.title.keyword",
            "path": "creators"
        }
    }
    ordering_fields = {
        "title": "group.title",
        "start_date": "group.dates.begin",
        "end_date": "group.dates.end",
        "creator": {
            "field": "group.creators.title.keyword",
            "path": "group.creators"
        }
    }
    search_fields = ("title", "description", "type", "")
    search_nested_fields = {
        "notes": {"path": "notes", "fields": ["subnotes.content"]},
    }

    def get_queryset(self):
        """Uses `collapse` to group hits based on `group` attribute."""
        collapse_params = {
            "field": "group.identifier",
            "inner_hits": {
                "size": 0,
                "name": "collection_hits",
                "_source": False
            }
        }
        a = A("cardinality", field="group.identifier")
        self.search.aggs.bucket("total", a)
        return self.search.extra(collapse=collapse_params).query()


class FacetView(SearchView):
    """Returns facets based on search terms."""
    serializer = FacetSerializer

    def get_queryset(self):
        """Adds aggregations and sets an empty size to return only facets."""
        creator = A("nested", path="creators")
        creator_name = A("terms", field="creators.title.keyword", size=100)
        subject = A("nested", path="terms")
        subject_name = A("terms", field="terms.title.keyword", size=100)
        format = A("terms", field="formats.keyword")
        max_date = A("max", field="dates.end", format="epoch_millis")
        min_date = A("min", field="dates.begin", format="epoch_millis")
        online = A('filter', Q('terms', online=[True]))
        self.search.aggs.bucket('creator', creator).bucket("name", creator_name)
        self.search.aggs.bucket('subject', subject).bucket("name", subject_name)
        self.search.aggs.bucket('format', format)
        self.search.aggs.bucket("max_date", max_date)
        self.search.aggs.bucket("min_date", min_date)
        self.search.aggs.bucket("online", online)
        return self.search.extra(size=0)

    def retrieve(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        results = queryset.execute()
        serializer = self.get_serializer(results)
        return Response(serializer.data)
