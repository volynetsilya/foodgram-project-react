from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import (CustomUserViewSet, FavoriteRecipeViewSet,
                    IngredientViewSet, RecipeViewSet, ShoppingCartViewSet,
                    SubscriptionViewSet, TagViewSet)

app_name = 'api'

router = DefaultRouter()
router.register('users', CustomUserViewSet, basename='users')
router.register('recipes', RecipeViewSet, basename='recipes')
router.register('ingredient', IngredientViewSet, basename='ingredient')
router.register('tags', TagViewSet, basename='tags')
router.register(
    r'users/(?P<user_id>\d+)/subscribe', SubscriptionViewSet,
    basename='subscribe'
)
router.register(
    r'recipes/(?P<recipe_id>\d+)/favorite', FavoriteRecipeViewSet,
    basename='favorite'
)
router.register(
    r'recipes/(?P<recipe_id>\d+)/shopping_cart', ShoppingCartViewSet,
    basename='shopping_cart'
)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls.authtoken')),
    path('', include('djoser.urls')),
]
