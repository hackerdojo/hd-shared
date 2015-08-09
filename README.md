# Shared Resources

This is a collection of shared modules and resources for Hacker Dojo applications. It should be included as a submodule to all Dojo app repositories. 

## Including in a new Dojo app repo

It's recommended to point to the public canonical hd-shared repo as a directory called "shared" at the root of your Dojo app project directory. Here is the command to set it up:

    git submodule add git://github.com/hackerdojo/hd-shared.git shared

Now you will have access to these shared resources in your Dojo project under the "shared" directory.
