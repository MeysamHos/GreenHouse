from django.db.models import F, Count
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic
from django.utils import timezone

from .models import Choice, Question

# Create your views here.

class IndexView(generic.ListView):
    template_name = "polls/index.html"
    context_object_name = "latest_question_list"

    def get_queryset(self):
        """
        Return the last five published questions (not including those set to be
        published in the future) AND ensure they have at least one choice.
        """
        return (
            Question.objects.filter(pub_date__lte=timezone.now())
            .annotate(num_choices=Count("choice"))  # Count the related choices
            .filter(num_choices__gt=0)              # Filter out questions with 0 choices
            .order_by("-pub_date")[:5]
        )

class DetailView(generic.DetailView):
    model = Question
    template_name = "polls/detail.html"

    def get_queryset(self):
        """
        Excludes any questions that aren't published yet or don't have choices.
        """
        return (
            Question.objects.filter(pub_date__lte=timezone.now())
            .annotate(num_choices=Count("choice"))
            .filter(num_choices__gt=0)
        )


class ResultsView(generic.DetailView):
    model = Question
    template_name = "polls/results.html"
    
    def get_queryset(self):
        """
        Ensure users can't see results for choice-less or future questions via URL manipulation.
        """
        return (
            Question.objects.filter(pub_date__lte=timezone.now())
            .annotate(num_choices=Count("choice"))
            .filter(num_choices__gt=0)
        )


def vote(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    try:
        selected_choice = question.choice_set.get(pk=request.POST["choice"])
    except (KeyError, Choice.DoesNotExist):
        # Redisplay the question voting form.
        return render(
            request,
            "polls/detail.html",
            {
                "question": question,
                "error_message": "You didn't select a choice.",
            },
        )
    else:
        selected_choice.votes = F("votes") + 1
        selected_choice.save()
        # Always return an HttpResponseRedirect after successfully dealing
        # with POST data. This prevents data from being posted twice if a
        # user hits the Back button.
        return HttpResponseRedirect(reverse("polls:results", args=(question.id,)))

def detail(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    return render(request, "polls/detail.html", {"question": question})