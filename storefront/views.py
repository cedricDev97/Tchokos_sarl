from django.shortcuts import render

def home(request):
    return render(request, "storefront/index.html")



# Create your views here.
