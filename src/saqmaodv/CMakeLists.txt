build_lib(
  LIBNAME saqmaodv
  SOURCE_FILES
    model/saqmaodv-rtable.cc
    model/saqmaodv-rqueue.cc
    model/saqmaodv-packet.cc
    model/saqmaodv-qtable.cc
    model/saqmaodv-routing-protocol.cc
    model/saqmaodv-neighbor.cc
    model/saqmaodv-dpd.cc
    model/saqmaodv-id-cache.cc
    helper/saqmaodv-helper.cc
  HEADER_FILES
    model/saqmaodv-rtable.h
    model/saqmaodv-rqueue.h
    model/saqmaodv-packet.h
    model/saqmaodv-qtable.h
    model/saqmaodv-routing-protocol.h
    model/saqmaodv-neighbor.h
    model/saqmaodv-dpd.h
    model/saqmaodv-id-cache.h
    helper/saqmaodv-helper.h
  LIBRARIES_TO_LINK
    ${libcore} ${libnetwork} ${libinternet}
    ${libwifi} ${libenergy} ${libmobility}
)
