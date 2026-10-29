# -*- coding: utf-8 -*-
"""Reviewed official GUI interface identities, not renderer implementations."""
from __future__ import absolute_import


class RecipeUpdateListener(object):
    def __init__(self):
        if self.__class__ is RecipeUpdateListener:
            raise TypeError('RecipeUpdateListener is an interface')

    def recipesUpdated(self, _nc_java_signature=None):
        raise NotImplementedError('RecipeUpdateListener requires recipesUpdated implementation')

    def getRecipeBookComponent(self, _nc_java_signature=None):
        raise NotImplementedError('RecipeUpdateListener requires getRecipeBookComponent implementation')


RECIPE_UPDATE = 'net.minecraft.client.gui.screens.recipebook.RecipeUpdateListener'
INTERFACE_CONTRACTS = {RECIPE_UPDATE: dict(abi=1, java_name=RECIPE_UPDATE,
    methods=[dict(name='recipesUpdated', parameters=[], return_type='void',
        static=False, abstract=True, visibility='public'),
        dict(name='getRecipeBookComponent', parameters=[], return_type='net.minecraft.client.gui.screens.recipebook.RecipeBookComponent',static=False,abstract=True,visibility='public')])}
INTERFACE_TYPES = {RECIPE_UPDATE: RecipeUpdateListener}
JAVA_MAP = {RECIPE_UPDATE: RecipeUpdateListener}
