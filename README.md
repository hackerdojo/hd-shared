# Shared Resources

This is a collection of shared modules and resources for other Dojo applications. It should be included
as a submodule to all Dojo app repositories. It's recommended to keep it pointed to the public canonical
Hacker Dojo repo as a directory called "shared" at the root of your project directory. Like so:

    git submodule add git://github.com/hackerdojo/hd-shared.git shared

which will give you a .submodule file that looks like this:

    [submodule "shared"]
        path = shared
        url = git://github.com/hackerdojo/hd-shared.git

## Running Tests

This project requires [fabric](http://docs.fabfile.org/0.9.3/installation.html), [nose](http://somethingaboutorange.com/mrl/projects/nose/1.0.0/), the [nosegae](http://farmdev.com/projects/nosegae/) plugin, as well as the [App Engine SDK](http://code.google.com/appengine/downloads.html). Assuming you have everything
installed, you can just run this in the project path:

    fab test