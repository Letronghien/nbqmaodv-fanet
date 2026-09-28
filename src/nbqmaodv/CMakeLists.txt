build_lib(
  LIBNAME nbqmaodv
  SOURCE_FILES
    model/nbqmaodv-rtable.cc
    model/nbqmaodv-rqueue.cc
    model/nbqmaodv-packet.cc
    model/nbqmaodv-qtable.cc
    model/nbqmaodv-routing-protocol.cc
    model/nbqmaodv-neighbor.cc
    model/nbqmaodv-dpd.cc
    model/nbqmaodv-id-cache.cc
    helper/nbqmaodv-helper.cc
  HEADER_FILES
    model/nbq-learning.h
    model/nbqmaodv-rtable.h
    model/nbqmaodv-rqueue.h
    model/nbqmaodv-packet.h
    model/nbqmaodv-qtable.h
    model/nbqmaodv-routing-protocol.h
    model/nbqmaodv-neighbor.h
    model/nbqmaodv-dpd.h
    model/nbqmaodv-id-cache.h
    helper/nbqmaodv-helper.h
  LIBRARIES_TO_LINK
    ${libcore} ${libnetwork} ${libinternet}
    ${libwifi} ${libenergy} ${libmobility}
)
