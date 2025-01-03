#import reminder form

from django.db.models.base import Model as Model
from django.db.models.query import QuerySet
from django.shortcuts import render, redirect, get_object_or_404
from .forms import CustomUserCreationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import HttpResponse, JsonResponse
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from .models import Checklist, Listitem, Reminder, List_user
from django.contrib.auth.models import User
from .forms import ChecklistForm, ListitemForm, UserEditForm, ReminderForm, ShareChecklistForm
from django.core.mail import send_mail
from django.contrib.admin.views.decorators import staff_member_required
import datetime


# Create your views here.
@login_required
def home(request):
    if 'logout' in request.GET:
        logout(request)
        return redirect('login')
    owned_checklists = Checklist.objects.filter(owner=request.user)
    shared_checklists = Checklist.objects.filter(
    id__in=List_user.objects.filter(user=request.user).values_list('checklist_id', flat=True)
    )

    return render(request, 'home.html', {
        'owned_checklists': owned_checklists,
       'shared_checklists': shared_checklists,
    })

def welcome(request):
    if request.user:
        return redirect('home')
    else:  
        return render(request, 'welcome.html')


def signup(request):
    error_message = ''
    if request.method == 'POST':
        # Create a user form object with POST data
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Add the user to the database
            user = form.save(commit=False)
            user.email = form.cleaned_data.get('email')  # Save the email
            user.save()
            # Log the user in
            login(request, user)
            return redirect('welcome')  # Redirect to a welcome page or dashboard
        else:
            error_message = 'Invalid sign up - try again'
    else:
        # Render signup.html with an empty form
        form = CustomUserCreationForm()
    
    # Render the signup page with form and potential error message
    context = {'form': form, 'error_message': error_message}
    return render(request, 'signup.html', context)


#checklist create view
class ChecklistCreate(LoginRequiredMixin, CreateView):
    model = Checklist
    form_class = ChecklistForm
    template_name = 'main_app/checklist_form.html'
    #success_url = '/checklists/'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form) # Calls form.save() internally
    
    def get_success_url(self):
        return reverse_lazy('home')

#view of all checklists
@login_required
def checklist_index(request):#Do we need this?
    owned_checklists = Checklist.objects.filter(owner=request.user)
    shared_checklists = Checklist.objects.filter(
        id__in=List_user.objects.filter(user=request.user).values_list('checklist_id', flat=True)
    )



    return render(request, 'checklists/index.html', {
        'owned_checklists': owned_checklists,
        'shared_checklists': shared_checklists,
    })

#view of one checklist
@login_required
def checklist_detail(request, checklist_id):#Do we need this?
    checklist = get_object_or_404(Checklist, id=checklist_id)
    list_user = get_object_or_404(List_user, checklist=checklist_id)
    

    # if (checklist.owner != request.user):
    #     return HttpResponse('You are not authorized to view this checklist', status=403)
    if (checklist.owner == request.user) or (list_user.user == request.user):
        tasks = checklist.listitem_set.all()
        return render(request, 'checklists/detail.html', {
            'checklist': checklist,
            'tasks': tasks,
        })
    
    else:
        return HttpResponse('You are not authorized to view this checklist', status=403)
      


#edit checklist
class ChecklistUpdate(LoginRequiredMixin, UpdateView):
    model = Checklist
    fields = ['list_name', 'status']
    template_name = 'main_app/checklist_form.html'

    def get_object(self, queryset=None):
        checklist = super().get_object(queryset)
    
        if checklist.owner != self.request.user:
            raise HttpResponse('You are not authorized to edit this checklist.')

        return checklist

    def get_success_url(self) -> str:
        return reverse_lazy('home')

#delete checklist
class ChecklistDelete(LoginRequiredMixin, DeleteView):
    model = Checklist
    success_url = '/home/'
    template_name = 'main_app/checklist_confirm_delete.html'

    def get_object(self, queryset=None):
        checklist = super().get_object(queryset)
        if checklist.owner != self.request.user:
            raise HttpResponse('You are not authorized to edit this checklist.')
        
        return checklist

@login_required
def add_task_to_checklist(request, checklist_id):
    checklist = get_object_or_404(Checklist, id=checklist_id)

    if checklist.owner != request.user:
        list_user = List_user.objects.filter(user=request.user, checklist=checklist).first()
        if not list_user or list_user.role != 'E':
            raise HttpResponse('You are not authorized to add tasks to this checklist.')


    if request.method == 'POST':
        form = ListitemForm(request.POST)
        if form.is_valid():
            listitem = form.save(commit=False)
            listitem.checklist = checklist
            listitem.save()
            return redirect('home')
    else:
        form = ListitemForm()

    return render(request, 'checklists/add_task.html', {
        'form': form,
        'checklist': checklist,
    })    

class ListitemUpdate(LoginRequiredMixin, UpdateView):
    model = Listitem
    form_class = ListitemForm
    template_name = 'checklists/edit_task.html'

    def get_object(self, queryset=None):
        task = super().get_object(queryset)

        if task.checklist.owner != self.request.user:
            raise HttpResponse('You do not have permission to edit this task.')
        
        return task

    def get_success_url(self):
        checklist_id = self.object.checklist.id
        return reverse_lazy('home')


class ListitemDelete(LoginRequiredMixin, DeleteView):
    model = Listitem
    template_name = 'main_app/task_confirm_delete.html'

    def get_object(self, queryset=None):
        task = super().get_object(queryset)

        if task.checklist.owner != self.request.user:
            raise HttpResponse('You do not have permission to delete this task.')
        
        return task

    def get_success_url(self):
        checklist_id = self.object.checklist.id
        return reverse_lazy('home')


@login_required
def get_checklist_tasks(request, checklist_id):
    checklist = get_object_or_404(Checklist, id=checklist_id)
    tasks = checklist.listitem_set.all()

    task_data = []
    for task in tasks:
        task_data.append({
            'step_name': task.step_name,
            'status': task.get_status_display(),
            'description': task.description,
            'priority': "High" if task.high_priority else "Low",
            'edit_url': f"{request.scheme}://{request.get_host()}/checklists/{task.checklist.id}/edit-task/{task.id}/",
            'new_reminder_url': f"{request.scheme}://{request.get_host()}/checklists/{task.checklist.id}/new-reminder/{task.id}"
        })
    return JsonResponse({'tasks': task_data})    

@login_required
def user_detail(request):
    return render(request, 'users/user_detail.html', {'user': request.user})


@login_required
def edit_user(request):
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('user_detail')  # Redirect to the user detail page
    else:
        form = UserEditForm(instance=request.user)  # Pre-fill with the current user's data
    return render(request, 'users/edit_user.html', {'form': form})



#mailer
@staff_member_required
def mailer(request):
    
    #try
    try:
        #get all reminders for tomorrow
        #if reminder date equals today and reminder has not been sent
        reminders = Reminder.objects.filter(reminder_date__lt=datetime.now(), reminder_sent=False)
        now = datetime.datetime.now()
        #for all reminders
        for reminder in reminders:          
            
            #send reminder
            send_mail(
                f"Reminder for {reminder.list_item}",
                f"This is a reminder for {reminder.list_item}, it is currently {reminder.status}.",
                "tasker.reminders@gmail.com",
                [request.user.email],
                fail_silently=False
            )
            #mark reminder as sent
            reminder.reminder_sent = True
            #when done reply with ok it worked
            print(f"Reminder sent to {request.user} for {reminder.list_item}")
            return HttpResponse(status=200)
    #except
    except:
        #if an error occurs reply with error
        return HttpResponse(status=500)


#define create reaminder args. request, user_id, list_item_id
@login_required
def create_reminder(request,checklist_id, list_item_id):
    #get specific list item remindeer is being created for
    list_item = get_object_or_404(Listitem, id=list_item_id)
    checklist = get_object_or_404(Checklist, id=checklist_id)
     
    form = ReminderForm()
    if request.user == checklist.owner:
        #check to see if request method is post
        if request.method == 'POST':
            #creat from instance
            form = ReminderForm(request.POST)
            #check to see if form is_valid()
            if form.is_valid():            
                #create new reminder variable but do not save anything to it
                reminder = form.save(commit=False)            
                #Add user_id to new reminder
                reminder.user = request.user
                #Add list_item_id to new reminder
                reminder.list_item = list_item
                #save new reminder
                reminder.save()
                #redirect to list detail
                return redirect('home')
            else:
                form = ReminderForm()

        return render(request, 'reminders/new_reminder.html', {
        'form': form,
        'list_item': list_item,
        'checklist': checklist
    })






#reminders index view
@login_required
def reminder_index(request):       
    reminders = Reminder.objects.filter(user=request.user)    
    return render(request, 'reminders/index.html', {'reminders': reminders})

#Delete reminder view

class ReminderConfirmDeleteView(LoginRequiredMixin, DeleteView):
    model = Reminder
    template_name = 'reminders/reminder_confirm_delete.html'
    success_url = '/reminders/'

           
# Share checklist view
@login_required
def share_checklist(request, checklist_id):
    checklist = get_object_or_404(Checklist, id=checklist_id)

    # Ensure the logged-in user is the owner
    if checklist.owner != request.user:
        return HttpResponse('You are not authorized to share this checklist.', status=403)

    if request.method == 'POST':
        form = ShareChecklistForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            role = form.cleaned_data['role']

            try:
                user_to_share = User.objects.get(username=username)

                # Prevent sharing with oneself
                if user_to_share == request.user:
                    return HttpResponse('You cannot share a checklist with yourself.', status=400)

                # Check if already shared
                if List_user.objects.filter(user=user_to_share, checklist=checklist).exists():
                    return HttpResponse('User already has access to this checklist.', status=400)

                # Share checklist
                List_user.objects.create(user=user_to_share, checklist=checklist, role=role)
                return redirect('share-checklist', checklist_id=checklist_id)  # Redirect back to the share-list page

            except User.DoesNotExist:
                return HttpResponse('User not found.', status=404)
    else:
        form = ShareChecklistForm()

    # Fetch shared users to display
    shared_users = List_user.objects.filter(checklist=checklist)

    return render(request, 'checklists/share_checklist.html', {
        'checklist': checklist,
        'form': form,
        'shared_users': shared_users,
    })


# Deactivate account
@login_required
def deactivate_account(request):
    
    if request.method == 'POST':
        # Mark the user as inactive
        user = request.user
        user.is_active = False
        user.save()

        # Log the user out after deactivating the account
        from django.contrib.auth import logout
        logout(request)
        return redirect('goodbye')  
    return render(request, 'users/deactivate_confirm.html')

def goodbye_page(request):
    return render(request, 'users/goodbye.html')